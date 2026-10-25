"""Integration against a real Superset, authenticating by session (cookie + CSRF) unless stated otherwise.

Server behavior is tested here, against the real Superset; tests/unit mocks HTTP only for conditions the
server cannot produce deterministically (see AGENTS.md).

Test stack (docker-compose.yml, configured by the .env copied from .env.example):
    docker compose -p superset-api-plus up -d --build
    SUPERSET_INTEGRATION=1 pytest tests/integration -v
    docker compose -p superset-api-plus down -v

Another instance: set SUPERSET_URL, SUPERSET_USERNAME, SUPERSET_PASSWORD and, for the tests that
register a database, SUPERSET_TEST_DATABASE_URI (URI as seen by the Superset server).

The tests create their own objects (prefix "zz-superset-api-plus-test") and remove them at the end.
"""
import importlib
import os
import uuid

import pytest

from supersetapiplus.core.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.client import SupersetClient
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.exceptions import BadRequestError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter


def config(name: str, fallback: str | None = None, default: str | None = None) -> str | None:
    return os.getenv(name) or (os.getenv(fallback) if fallback else None) or default


ENABLED = bool(os.getenv("SUPERSET_URL") or os.getenv("SUPERSET_INTEGRATION"))
URL = config("SUPERSET_URL", default=f"http://127.0.0.1:{os.getenv('SUPERSET_TEST_PORT', '8089')}")
USERNAME = config("SUPERSET_USERNAME", "SUPERSET_ADMIN_USERNAME")
PASSWORD = config("SUPERSET_PASSWORD", "SUPERSET_ADMIN_PASSWORD")
# Secret of the test stack: signs the expired token of the JWT renewal test.
SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY")
DATABASE_URI = config("SUPERSET_TEST_DATABASE_URI") or (
    "postgresql://{u}:{p}@pg:5432/{d}".format(u=os.getenv("POSTGRES_USER"), p=os.getenv("POSTGRES_PASSWORD"),
                                             d=os.getenv("POSTGRES_DB", "tests"))
    if os.getenv("POSTGRES_USER") and os.getenv("POSTGRES_PASSWORD") else None)

# Tests that change the instance users (403 with a Gamma user) run only on the local test stack.
only_test_stack = pytest.mark.skipif(bool(os.getenv("SUPERSET_URL")),
                                     reason="creates users: local test stack only")

PREFIX = "zz-superset-api-plus-test"
SQL_DATASET = ("select 'North' as campus, 10 as total, date '2026-01-01' as day "
               "union all select 'South', 7, date '2026-01-02'")


def pytest_collection_modifyitems(config, items):
    if ENABLED and USERNAME and PASSWORD:
        return
    skip = pytest.mark.skip(reason="set SUPERSET_INTEGRATION=1 (test stack) or SUPERSET_URL and credentials")
    for item in items:
        if "tests/integration" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(skip)


def unique_name(suffix: str) -> str:
    return f"{PREFIX}-{suffix}-{uuid.uuid4().hex[:6]}"


def name_filter(column: str, value: str, operator: QueryOperator = QueryOperator.EQUAL) -> QueryStringFilter:
    query_filter = QueryStringFilter()
    query_filter.add(column, operator, value)
    return query_filter


def new_client(session_mode: bool = True, username: str | None = None, password: str | None = None) -> SupersetClient:
    client = SupersetClient(URL, username or USERNAME, password or PASSWORD, verify=URL.startswith("https"))
    if session_mode:
        client.enable_session_mode()
    return client


@pytest.fixture(scope="session")
def client():
    return new_client()


@pytest.fixture(scope="session")
def database(client):
    if not DATABASE_URI:
        pytest.skip("set SUPERSET_TEST_DATABASE_URI or the stack POSTGRES_USER/POSTGRES_PASSWORD")
    db = Database(database_name=unique_name("db"), sqlalchemy_uri=DATABASE_URI, expose_in_sqllab=True)
    client.databases.add(db)
    yield db
    client.databases.delete(db.id)


@pytest.fixture(scope="session")
def dataset(client, database):
    ds = Dataset(table_name=unique_name("ds"), schema="public", sql=SQL_DATASET, database_id=database.id)
    client.datasets.add(ds)
    yield ds
    client.datasets.delete(ds.id)


def new_chart(viz_type: str, dataset: Dataset, slice_name: str | None = None) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=slice_name or unique_name(viz_type), datasource=DataSource(id=dataset.id, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    return chart


class Cleanup:
    """Removes, at the end of the test, the dashboards, charts, datasets and CSS templates it created, in this
    order (a dataset with charts cannot be removed); ignores those already removed."""

    def __init__(self, client: SupersetClient):
        self.client, self.charts, self.dashboards, self.datasets, self.css_templates = client, [], [], [], []

    def chart(self, chart_id: int) -> int:
        self.charts.append(chart_id)
        return chart_id

    def dashboard(self, dashboard_id: int) -> int:
        self.dashboards.append(dashboard_id)
        return dashboard_id

    def dataset(self, dataset_id: int) -> int:
        self.datasets.append(dataset_id)
        return dataset_id

    def css_template(self, template_id: int) -> int:
        self.css_templates.append(template_id)
        return template_id

    def run(self) -> None:
        for factory, ids in ((self.client.dashboards, self.dashboards), (self.client.charts, self.charts),
                             (self.client.datasets, self.datasets), (self.client.css_templates, self.css_templates)):
            for pk in ids:
                try:
                    factory.delete(pk)
                except BadRequestError:
                    pass


@pytest.fixture
def cleanup(client):
    tracker = Cleanup(client)
    yield tracker
    tracker.run()


@pytest.fixture
def add_chart(client, dataset, cleanup):
    """Creates a chart of `viz_type` on the test dataset and registers it for removal."""
    def create(viz_type: str = "table", slice_name: str | None = None) -> Chart:
        chart = new_chart(viz_type, dataset, slice_name)
        cleanup.chart(client.charts.add(chart))
        return chart
    return create


@pytest.fixture
def unmodeled_chart(client, dataset, cleanup):
    """Chart of a viz_type the library does not model, created through the raw API."""
    payload = {"slice_name": unique_name("unmodeled"), "viz_type": "sankey_v2", "datasource_id": dataset.id,
               "datasource_type": "table", "params": '{"viz_type": "sankey_v2"}'}
    return cleanup.chart(client.post(client.charts.base_url, json=payload).json()["id"])

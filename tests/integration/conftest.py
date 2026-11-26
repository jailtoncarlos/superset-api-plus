"""Integration against a real Superset, authenticating by session (cookie + CSRF) unless stated otherwise.

Server behavior is tested here, against the real Superset; tests/unit mocks HTTP only for conditions the
server cannot produce deterministically (see AGENTS.md).

Test stack (docker-compose.yml, configured by the .env copied from .env.example):
    docker compose -p superset-api-plus up -d --build
    SUPERSET_INTEGRATION=1 pytest tests/integration -v
    docker compose -p superset-api-plus down -v

Another instance: set SUPERSET_URL, SUPERSET_USERNAME, SUPERSET_PASSWORD and, for the tests that
register a database, SUPERSET_TEST_DATABASE_URI (URI as seen by the Superset server); SUPERSET_LOGIN_PATH when the
database login form is not at /login/ (e.g. the test stack with SUPERSET_TEST_AUTH_TYPE=oauth).

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
from supersetapiplus.resources.repository import SoftDeleteRepository

from .known_7_0_gaps import KNOWN_7_0_GAPS


def config(name: str, fallback: str | None = None, default: str | None = None) -> str | None:
    return os.getenv(name) or (os.getenv(fallback) if fallback else None) or default


ENABLED = bool(os.getenv("SUPERSET_URL") or os.getenv("SUPERSET_INTEGRATION"))
URL = config("SUPERSET_URL", default=f"http://127.0.0.1:{os.getenv('SUPERSET_TEST_PORT', '8089')}")
USERNAME = config("SUPERSET_USERNAME", "SUPERSET_ADMIN_USERNAME")
PASSWORD = config("SUPERSET_PASSWORD", "SUPERSET_ADMIN_PASSWORD")
# Path of the login form of session mode: the test stack in OAuth mode (SUPERSET_TEST_AUTH_TYPE=oauth) is logged in
# through its service route, /service-login/login/.
LOGIN_PATH = config("SUPERSET_LOGIN_PATH")
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


@pytest.fixture(autouse=True)
def known_7_0_gap(request, client):
    """Marks the tests of known_7_0_gaps.py xfail(strict=True) on a Superset 7.0 server (see that module)."""
    reason = KNOWN_7_0_GAPS.get(f"{request.node.path.name}::{request.node.originalname}")
    if reason and int(client.server_version.split(".")[0]) >= 7:
        request.applymarker(pytest.mark.xfail(reason=f"known Superset 7.0 gap: {reason}", strict=True))


def purge_archived(client: SupersetClient) -> None:
    """On Superset 7.0 (soft delete), deletes permanently the archived dashboards, charts and datasets the tests
    created (prefix PREFIX): a deleted object is only archived, and a database whose datasets are archived cannot be
    deleted. Nothing to do before 7.0."""
    if int(client.server_version.split(".")[0]) < 7:
        return
    for repository, column in ((client.dashboards, "dashboard_title"), (client.charts, "slice_name"),
                               (client.datasets, "table_name")):
        for obj in repository.find_archived(name_filter(column, PREFIX, QueryOperator.STARTS_WITH)):
            try:
                repository.purge(obj.uuid)
            except BadRequestError:  # already purged with the dataset it depended on
                pass


def name_filter(column: str, value: str, operator: QueryOperator = QueryOperator.EQUAL) -> QueryStringFilter:
    query_filter = QueryStringFilter()
    query_filter.add(column, operator, value)
    return query_filter


def new_client(session_mode: bool = True, username: str | None = None, password: str | None = None) -> SupersetClient:
    client = SupersetClient(URL, username or USERNAME, password or PASSWORD, verify=URL.startswith("https"))
    if session_mode:
        client.enable_session_mode(LOGIN_PATH)
    return client


@pytest.fixture(scope="session")
def client():
    return new_client()


@pytest.fixture(scope="session")
def chromium():
    """Skips the test when Playwright (extra ``browser``) or its Chromium is not installed; with
    ``SUPERSET_BROWSER_REQUIRED=1`` (the CI) it fails instead. ``CHROME_PATH`` selects the executable."""
    missing = pytest.fail if os.getenv("SUPERSET_BROWSER_REQUIRED") == "1" else pytest.skip
    try:
        from playwright import sync_api
    except ImportError:
        missing("Playwright is not installed (extra 'browser')")
    try:
        with sync_api.sync_playwright() as playwright:
            playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None).close()
    except Exception as error:  # noqa: BLE001 (any launch failure means no usable browser)
        missing(f"Chromium cannot be launched: {error}")


@pytest.fixture(scope="session")
def database(client):
    if not DATABASE_URI:
        pytest.skip("set SUPERSET_TEST_DATABASE_URI or the stack POSTGRES_USER/POSTGRES_PASSWORD")
    db = Database(database_name=unique_name("db"), sqlalchemy_uri=DATABASE_URI, expose_in_sqllab=True)
    client.databases.add(db)
    yield db
    purge_archived(client)  # archived datasets of the database would block its deletion
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
    """Removes, at the end of the test, the row level security rules, dashboards, charts, datasets, CSS templates and
    roles it created, in this order (a dataset with charts cannot be removed); ignores those already removed."""

    def __init__(self, client: SupersetClient):
        self.client, self.charts, self.dashboards, self.datasets = client, [], [], []
        self.css_templates: list[int] = []
        self.roles: list[int] = []
        self.rls_rules: list[int] = []

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

    def role(self, role_id: int) -> int:
        self.roles.append(role_id)
        return role_id

    def rls_rule(self, rule_id: int) -> int:
        self.rls_rules.append(rule_id)
        return rule_id

    def run(self) -> None:
        for factory, ids in ((self.client.row_level_security, self.rls_rules),
                             (self.client.dashboards, self.dashboards), (self.client.charts, self.charts),
                             (self.client.datasets, self.datasets), (self.client.css_templates, self.css_templates),
                             (self.client.roles, self.roles)):
            for pk in ids:
                try:
                    # Read raw: the object may be of a type the library does not model (unmodeled viz_type).
                    uuid_ = (self.client.get(factory.object_url(pk)).json()["result"].get("uuid")
                             if isinstance(factory, SoftDeleteRepository) else None)
                    factory.delete(pk)
                    if uuid_ and int(self.client.server_version.split(".")[0]) >= 7:
                        factory.purge(uuid_)  # Superset 7.0 archives it: a later run could not reuse its name
                except BadRequestError:
                    pass
        purge_archived(self.client)  # what the tests deleted themselves (archived, with the test prefix)


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

"""Integration against a real Superset, authenticating by session (cookie + CSRF).

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
import zipfile

import pytest

from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.exceptions import BadRequestError, NotFound
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.saved_queries import SavedQuery


def config(name: str, fallback: str | None = None, default: str | None = None) -> str | None:
    return os.getenv(name) or (os.getenv(fallback) if fallback else None) or default


ENABLED = bool(os.getenv("SUPERSET_URL") or os.getenv("SUPERSET_INTEGRATION"))
URL = config("SUPERSET_URL", default=f"http://127.0.0.1:{os.getenv('SUPERSET_TEST_PORT', '8089')}")
USERNAME = config("SUPERSET_USERNAME", "SUPERSET_ADMIN_USERNAME")
PASSWORD = config("SUPERSET_PASSWORD", "SUPERSET_ADMIN_PASSWORD")
DATABASE_URI = config("SUPERSET_TEST_DATABASE_URI") or (
    "postgresql://{u}:{p}@pg:5432/{d}".format(u=os.getenv("POSTGRES_USER"), p=os.getenv("POSTGRES_PASSWORD"),
                                             d=os.getenv("POSTGRES_DB", "tests"))
    if os.getenv("POSTGRES_USER") and os.getenv("POSTGRES_PASSWORD") else None)

pytestmark = pytest.mark.skipif(not (ENABLED and USERNAME and PASSWORD),
                                reason="set SUPERSET_INTEGRATION=1 (test stack) or SUPERSET_URL and credentials")

PREFIX = "zz-superset-api-plus-test"
SQL_DATASET = "select 'North' as campus, 10 as total union all select 'South', 7"


def unique_name(suffix: str) -> str:
    return f"{PREFIX}-{suffix}-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def client():
    client = SupersetClient(URL, USERNAME, PASSWORD, verify=URL.startswith("https"))
    client.enable_session_mode()
    return client


@pytest.fixture(scope="module")
def database(client):
    if not DATABASE_URI:
        pytest.skip("set SUPERSET_TEST_DATABASE_URI or the stack POSTGRES_USER/POSTGRES_PASSWORD")
    db = Database(database_name=unique_name("db"), sqlalchemy_uri=DATABASE_URI, expose_in_sqllab=True)
    client.databases.add(db)
    yield db
    client.databases.delete(db.id)


@pytest.fixture(scope="module")
def dataset(client, database):
    ds = Dataset(table_name=unique_name("ds"), schema="public", sql=SQL_DATASET, database_id=database.id)
    client.datasets.add(ds)
    yield ds
    client.datasets.delete(ds.id)


def new_chart(viz_type: str, dataset: Dataset) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=unique_name(viz_type), datasource=DataSource(id=dataset.id, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    return chart


# --- Authentication and reading -------------------------------------------------------------

def test_session_authenticates_and_lists(client):
    assert client.charts.count() >= 0
    assert client.dashboards.count() >= 0


def test_find_one_without_result_raises_not_found(client):
    query_filter = QueryStringFilter()
    query_filter.add("slice_name", QueryOperator.EQUAL, unique_name("missing"))

    with pytest.raises(NotFound):
        client.charts.find_one(query_filter)


# --- Database, dataset and saved query ------------------------------------------------------

def test_database_created_and_read(client, database):
    fetched = client.databases.get(database.id)

    assert fetched.database_name == database.database_name


def test_database_with_invalid_uri_is_rejected(client):
    with pytest.raises(BadRequestError):
        client.databases.add(Database(database_name=unique_name("db-invalid"), sqlalchemy_uri="not-a-uri"))


def test_dataset_created_updated_and_read(client, dataset):
    fetched = client.datasets.get(dataset.id)
    fetched.description = "changed by the tests"
    fetched.save()

    assert client.datasets.get(dataset.id).description == "changed by the tests"


def test_saved_query_created_and_deleted(client, database):
    saved_query = SavedQuery(label=unique_name("sq"), sql="select 1", db_id=database.id, schema="public")

    client.saved_queries.add(saved_query)
    try:
        assert client.saved_queries.get(saved_query.id).label == saved_query.label
    finally:
        assert client.saved_queries.delete(saved_query.id)


# --- Charts and dashboard --------------------------------------------------------------------

@pytest.mark.parametrize("viz_type", ["table", "pie"])
def test_chart_created_in_code_round_trips(client, dataset, viz_type):
    chart = new_chart(viz_type, dataset)

    client.charts.add(chart)
    try:
        fetched = client.charts.get(chart.id)
        assert str(fetched.viz_type) == viz_type
        assert fetched.datasource_id == dataset.id
        assert fetched.params.to_dict() == chart.params.to_dict()

        fetched.slice_name = f"{chart.slice_name}-changed"
        fetched.save()
        assert client.charts.get(chart.id).slice_name.endswith("-changed")
    finally:
        assert client.charts.delete(chart.id)


def test_dashboard_created_updated_and_deleted(client):
    dashboard = Dashboard(dashboard_title=unique_name("dash"))

    client.dashboards.add(dashboard)
    try:
        fetched = client.dashboards.get(dashboard.id)
        fetched.dashboard_title = f"{dashboard.dashboard_title}-changed"
        fetched.save()
        assert client.dashboards.get(dashboard.id).dashboard_title.endswith("-changed")
    finally:
        assert client.dashboards.delete(dashboard.id)


def test_exports_chart_as_zip(client, dataset, tmp_path):
    chart = new_chart("table", dataset)
    client.charts.add(chart)
    try:
        target = tmp_path / "chart.zip"
        client.charts.export([chart.id], target)

        with zipfile.ZipFile(target) as archive:
            assert any(n.endswith(".yaml") and "/charts/" in n for n in archive.namelist())
    finally:
        client.charts.delete(chart.id)


# --- SQL Lab -------------------------------------------------------------------------------

def test_runs_sql_through_the_database(client, database):
    columns, data = client.databases.get(database.id).run("select 1 as one")

    assert data == [{"one": 1}]


# --- Listing filters ------------------------------------------------------------------------

def test_library_operators_are_accepted_by_the_server(client):
    filters = client.get(client.join_urls(client.charts.base_url, "_info"), params={"q": "(keys:!(filters))"}).json()
    accepted = {op["operator"] for column in filters["filters"].values() for op in column}

    assert {op.value for op in QueryOperator} <= accepted


@pytest.mark.parametrize("operator,value", [(QueryOperator.NOT_EQUAL, "x"), (QueryOperator.CONTAINS, "zz"),
                                            (QueryOperator.STARTS_WITH, "zz"), (QueryOperator.IN, ["table"])])
def test_listing_with_operators_responds_without_error(client, operator, value):
    query_filter = QueryStringFilter()
    query_filter.add("viz_type" if operator in (QueryOperator.IN, QueryOperator.NOT_EQUAL) else "slice_name", operator, value)

    assert client.charts.count(query_filter) >= 0


def test_chart_is_associated_with_the_dashboard_through_the_layout(client, dataset):
    chart = new_chart("table", dataset)
    client.charts.add(chart)
    dashboard = Dashboard(dashboard_title=unique_name("dash-assoc"))
    client.dashboards.add(dashboard)
    try:
        dashboard.position.add_chart(chart, chart.slice_name, parent=dashboard.position.add_tab("Tab"))
        dashboard.save()
        client.dashboards.attach_charts(dashboard)

        assert [c.id for c in client.dashboards.get(dashboard.id).get_charts()] == [chart.id]
        assert client.charts.dashboard_ids(chart.id) == [dashboard.id]
    finally:
        client.dashboards.delete(dashboard.id)
        client.charts.delete(chart.id)

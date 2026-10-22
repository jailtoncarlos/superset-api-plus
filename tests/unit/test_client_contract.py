"""Public client contract: authentication, search, reading and writing via the REST API.

Safety net for package reorganization: the tests exercise only the public API (including the
parts used by external integrations) and check the requests that reach Superset, without
depending on the internal implementation. Synthetic payloads.
"""
import json
from urllib.parse import parse_qs, urlparse

import importlib

import pytest
import requests
import requests_mock as rm

from supersetapiplus.charts.charts import Chart
from supersetapiplus import client as client_module
from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import MultipleFound, NotFound, UnsupportedTypeError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

HOST = "https://superset.example"
API = f"{HOST}/api/v1"
TOKEN = "test-jwt"

# Actual Superset 6.1.0 /_info for charts: ChartRestApi declares add/edit_columns = ["slice_name"],
# but validates the body with ChartPostSchema/ChartPutSchema. That is why /_info is not usable as a filter.
CHART_INFO = {"add_columns": [{"name": "slice_name"}], "edit_columns": [{"name": "slice_name"}]}

# Fields accepted by the Superset 6.1.0 schemas (OpenAPI: ChartRestApi.post / ChartRestApi.put).
CHART_POST_ACCEPTED = {"cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
                      "datasource_name", "datasource_type", "description", "external_url", "is_managed_externally",
                      "owners", "params", "query_context", "query_context_generation", "slice_name", "viz_type"}
CHART_POST_REQUIRED = {"datasource_id", "datasource_type", "slice_name"}
CHART_PUT_ACCEPTED = (CHART_POST_ACCEPTED - {"datasource_name"}) | {"tags"}


def chart_payload(chart_id: int, viz_type: str = "table", slice_name: str = "Respondents per campus") -> dict:
    params = {"datasource": "1__table", "viz_type": viz_type, "query_mode": "aggregate",
              "groupby": ["campus"], "metrics": ["count"], "row_limit": 100}
    return {"id": chart_id, "slice_name": slice_name, "viz_type": viz_type,
            "params": json.dumps(params), "query_context": None}


def query_param(request) -> dict:
    return json.loads(parse_qs(urlparse(request.url).query)["q"][0])


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": TOKEN, "refresh_token": "r"})
        m.get(f"{API}/chart/_info", json=CHART_INFO)
        m.get(f"{API}/security/csrf_token/", json={"result": "csrf-api"})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robot", "password", verify=True)


def equals_filter(column: str, value) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(column, QueryOperator.EQUAL, value)
    return f


# --- Authentication -----------------------------------------------------------------------

def test_jwt_login_sends_credentials_and_uses_bearer(client, mock):
    mock.get(f"{API}/chart/", json={"count": 3, "result": []})

    assert client.charts.count() == 3

    login = next(r for r in mock.request_history if r.path.endswith("/security/login"))
    assert login.json() == {"username": "robot", "password": "password", "provider": "db", "refresh": True}
    assert mock.last_request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert mock.last_request.headers["X-CSRFToken"] == "csrf-api"


def test_session_mode_logs_in_via_form_with_csrf_in_the_same_session(mock, monkeypatch):
    # requests_mock does not store response cookies in the session jar; the callbacks play the role
    # of Superset, setting the cookie on the session created by the client.
    sessions = []

    class CapturedSession(requests.Session):
        def __init__(self):
            super().__init__()
            sessions.append(self)

    def set_cookie(value):
        def callback(request, context):
            sessions[-1].cookies.set("session", value, domain="superset.example", path="/")
            return '<form><input name="csrf_token" value="csrf-form"></form>'
        return callback

    monkeypatch.setattr(client_module.requests, "Session", CapturedSession)
    mock.get(f"{HOST}/login/", text=set_cookie("pre-login"))
    mock.post(f"{HOST}/login/", text=set_cookie("authenticated"))
    mock.get(f"{API}/chart/", json={"count": 0, "result": []})
    client = SupersetClient(HOST, "robot", "password", verify=True)

    client.enable_session_mode()
    client.charts.count()
    mock.delete(f"{API}/chart/9", json={"message": "OK"})
    client.charts.delete(9)

    get_login, post_login = [r for r in mock.request_history if r.path == "/login/"]
    assert parse_qs(post_login.text) == {"username": ["robot"], "password": ["password"], "csrf_token": ["csrf-form"]}
    assert "session=pre-login" in post_login.headers["Cookie"]
    assert "session=authenticated" in mock.last_request.headers["Cookie"]
    assert "Authorization" not in mock.last_request.headers
    assert not any(r.path.endswith("/security/login") for r in mock.request_history)
    # Cookie-based writes require the CSRF token ("The CSRF token is missing." in Superset 6.1.0).
    assert mock.last_request.method == "DELETE"
    assert mock.last_request.headers["X-CSRFToken"] == "csrf-api"
    assert mock.last_request.headers["Referer"] == f"{HOST}/"


# --- Search and read -----------------------------------------------------------------------

def test_find_sends_filters_and_pagination_and_returns_typed_charts(client, mock):
    mock.get(f"{API}/chart/", json={"count": 1, "result": [chart_payload(10)]})

    charts = client.charts.find(equals_filter("slice_name", "Respondents per campus"), page_size=50, page=2)

    assert query_param(mock.last_request) == {
        "page_size": 50, "page": 2, "columns": [],
        "filters": [{"col": "slice_name", "opr": "eq", "value": "Respondents per campus"}],
    }
    assert [type(c).__name__ for c in charts] == ["TableChart"]
    assert isinstance(charts[0], Chart) and charts[0].id == 10


def test_find_with_restricted_columns_returns_partial_objects(client, mock):
    # The listing only returns the requested columns (no params); the partial object is enough to get the id.
    mock.get(f"{API}/chart/", json={"count": 1, "result": [{"id": 10, "slice_name": "x", "viz_type": "table"}]})

    charts = client.charts.find(equals_filter("slice_name", "x"), columns=["id", "slice_name", "viz_type"])

    assert query_param(mock.last_request)["columns"] == ["id", "slice_name", "viz_type"]
    assert [c.id for c in charts] == [10]


def test_find_one_without_result_raises_not_found(client, mock):
    mock.get(f"{API}/chart/", json={"count": 0, "result": []})

    with pytest.raises(NotFound):
        client.charts.find_one(equals_filter("slice_name", "missing"))


def test_find_one_with_several_results_raises_multiple_found(client, mock):
    mock.get(f"{API}/chart/", json={"count": 2, "result": [chart_payload(1), chart_payload(2)]})

    with pytest.raises(MultipleFound):
        client.charts.find_one(equals_filter("viz_type", "table"))


def test_find_one_full_reloads_the_chart_by_id(client, mock):
    mock.get(f"{API}/chart/", json={"count": 1, "result": [{"id": 10, "slice_name": "x", "viz_type": "table"}]})
    mock.get(f"{API}/chart/10", json={"id": 10, "result": chart_payload(10)})

    chart = client.charts.find_one(equals_filter("slice_name", "x"), full=True)

    assert mock.last_request.path == "/api/v1/chart/10"
    assert chart.slice_name == "Respondents per campus"
    assert chart.params.groupby == ["campus"]


def test_get_resolves_the_class_from_viz_type(client, mock):
    mock.get(f"{API}/chart/7", json={"id": 7, "result": chart_payload(7, viz_type="pie")})

    chart = client.charts.get(7)

    assert type(chart).__name__ == "PieChart" and chart.id == 7


def test_get_of_unmodeled_viz_type_raises_unsupported_type(client, mock):
    mock.get(f"{API}/chart/8", json={"id": 8, "result": chart_payload(8, viz_type="histogram_v2")})

    with pytest.raises(UnsupportedTypeError):
        client.charts.get(8)


def test_chart_get_class_resolves_from_viz_type():
    # Current contract: the type module must be imported first (an explicit registry would remove this requirement).
    importlib.import_module("supersetapiplus.charts.table")
    assert Chart.get_class("table", "supersetapiplus.charts.table").__name__ == "TableChart"


# --- Writing -------------------------------------------------------------------------------

def test_add_sends_accepted_and_required_schema_fields_and_stores_the_id(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_payload(9)})
    mock.post(f"{API}/chart/", json={"id": 99, "result": {}})
    chart = client.charts.get(9)

    new_id = client.charts.add(chart)

    payload = mock.last_request.json()
    assert new_id == 99 and chart.id == 99
    assert "id" not in payload
    assert set(payload) <= CHART_POST_ACCEPTED
    assert CHART_POST_REQUIRED <= set(payload)
    assert payload["datasource_id"] == 1 and payload["datasource_type"] == "table"
    assert json.loads(payload["params"])["groupby"] == ["campus"]


def test_save_puts_to_its_own_id_with_schema_accepted_fields(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_payload(9)})
    mock.put(f"{API}/chart/9", json={"id": 9, "result": {}})
    chart = client.charts.get(9)
    chart.slice_name = "New title"

    chart.save()

    assert mock.last_request.method == "PUT" and mock.last_request.path == "/api/v1/chart/9"
    payload = mock.last_request.json()
    assert payload["slice_name"] == "New title"
    assert set(payload) <= CHART_PUT_ACCEPTED
    assert json.loads(payload["params"])["groupby"] == ["campus"]


def test_delete_returns_true_when_superset_confirms(client, mock):
    mock.delete(f"{API}/chart/9", json={"message": "OK"})

    assert client.charts.delete(9) is True


DASHBOARD_ACCEPTED = {"certification_details", "certified_by", "css", "dashboard_title", "external_url",
                     "is_managed_externally", "json_metadata", "owners", "position_json", "published", "roles", "slug"}


def test_dashboard_add_sends_only_schema_accepted_fields(client, mock):
    from supersetapiplus.dashboards.dashboards import Dashboard

    mock.get(f"{API}/dashboard/_info", json={"add_columns": [{"name": "dashboard_title"}]})
    mock.post(f"{API}/dashboard/", json={"id": 5, "result": {}})

    assert client.dashboards.add(Dashboard(dashboard_title="Panel")) == 5

    payload = mock.last_request.json()
    assert payload["dashboard_title"] == "Panel"
    assert set(payload) <= DASHBOARD_ACCEPTED
    assert isinstance(payload["json_metadata"], str) and isinstance(payload["position_json"], str)


def test_find_does_not_break_listing_on_unmodeled_type_item(client, mock):
    from supersetapiplus.base.base import UnsupportedObject

    mock.get(f"{API}/chart/", json={"count": 2, "result": [
        {"id": 1, "slice_name": "a", "viz_type": "table"},
        {"id": 2, "slice_name": "b", "viz_type": "echarts_timeseries_line"},
    ]})

    charts = client.charts.find(QueryStringFilter(), columns=["id", "slice_name", "viz_type"])

    assert [c.id for c in charts] == [1, 2]
    assert type(charts[0]).__name__ == "TableChart"
    assert isinstance(charts[1], UnsupportedObject) and charts[1].viz_type == "echarts_timeseries_line"

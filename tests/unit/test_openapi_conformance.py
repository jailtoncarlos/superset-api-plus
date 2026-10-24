"""Conformance with Superset's official OpenAPI specification (excerpt in tests/fixtures).

For every resource the library writes, the create (POST) and update (PUT) payloads must
contain only fields accepted by the `{Resource}RestApi.post/.put` schema, include the required
ones and respect the declared type. The routes called must exist with the method used.

To validate another Superset version, generate a new excerpt with bin/scripts/extract_openapi.py
and point SPEC to it.

HTTP is mocked on purpose: this module runs offline in the `superset-conformance` pre-commit hook and checks
the payloads against the versioned specification. That the real server accepts them is tested in
tests/integration.
"""
import json
import re
from pathlib import Path

import pytest
import requests_mock as rm

from supersetapiplus.charts.table import TableChart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.resources.css_templates import CssTemplate
from supersetapiplus.saved_queries import SavedQuery

SPEC = json.loads((Path(__file__).parent.parent / "fixtures" / "superset_openapi_6.1.0.json").read_text())
HOST = "https://superset.example"
API = f"{HOST}/api/v1"

JSON_TYPES = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict, "number": (int, float)}

PARAMS = {"datasource": "1__table", "viz_type": "table", "query_mode": "aggregate",
          "groupby": ["campus"], "metrics": ["count"], "row_limit": 100}

# Object as the user creates it (POST) and as it comes from the API in a GET (PUT), per resource.
RESOURCES = {
    "chart": ("ChartRestApi",
              lambda: TableChart.from_json({"slice_name": "New", "viz_type": "table", "params": json.dumps(PARAMS),
                                            "query_context": None, "datasource_id": 1, "datasource_type": "table"}),
              {"id": 9, "slice_name": "G", "viz_type": "table", "params": json.dumps(PARAMS), "query_context": None,
               "description": None, "cache_timeout": None, "dashboards": [], "url": "/explore/?slice_id=9",
               "thumbnail_url": "/t", "changed_on_delta_humanized": "1 day ago", "owners": [{"id": 1}],
               "tags": []}),
    "dashboard": ("DashboardRestApi",
                  lambda: Dashboard(dashboard_title="Panel", published=True, slug="panel"),
                  {"id": 9, "dashboard_title": "Panel", "published": True, "slug": "panel", "css": "",
                   "json_metadata": json.dumps({"color_scheme": "supersetColors"}),
                   "position_json": json.dumps({
                       "DASHBOARD_VERSION_KEY": "v2",
                       "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"], "parents": []},
                       "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": [], "parents": ["ROOT_ID"]}}),
                   "url": "/superset/dashboard/9/", "thumbnail_url": "/t", "owners": [], "roles": [],
                   "changed_by_name": "x", "charts": ["G"]}),
    "dataset": ("DatasetRestApi",
                lambda: Dataset(table_name="vw_answers", schema="analytics", database_id=1, sql="select 1"),
                {"id": 9, "table_name": "vw_answers", "schema": "analytics", "sql": "select 1", "kind": "virtual",
                 "description": None, "datasource_type": "table", "database": {"id": 1, "database_name": "dw"},
                 "columns": [{"column_name": "campus"}], "metrics": [], "owners": []}),
    "database": ("DatabaseRestApi",
                 lambda: Database(database_name="dw", sqlalchemy_uri="postgresql://u:p@h/db"),
                 {"id": 9, "database_name": "dw", "sqlalchemy_uri": "postgresql://u:XXXXXXXXXX@h/db",
                  "allow_ctas": False, "allow_cvas": False, "allow_dml": False, "allow_run_async": False,
                  "expose_in_sqllab": True, "extra": "{}", "backend": "postgresql"}),
    "saved_query": ("SavedQueryRestApi",
                    lambda: SavedQuery(label="Query", sql="select 1", db_id=1, schema="analytics"),
                    {"id": 9, "label": "Query", "sql": "select 1", "schema": "analytics", "description": "",
                     "database": {"id": 1}, "db_id": 1}),
    "css_template": ("CssTemplateRestApi",
                     lambda: CssTemplate(template_name="Panel", css=".header { color: #333; }"),
                     {"id": 9, "template_name": "Panel", "css": ".header { color: #333; }",
                      "changed_on_delta_humanized": "now"}),
}


def factory_for(client, resource):
    return {"chart": client.charts, "dashboard": client.dashboards, "dataset": client.datasets,
            "database": client.databases, "saved_query": client.saved_queries,
            "css_template": client.css_templates}[resource]


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "t"})
        m.get(f"{API}/security/csrf_token/", json={"result": "c"})
        m.get(re.compile(rf"{API}/\w+/_info"), json={"add_columns": [], "edit_columns": []})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robot", "password")


def violations(payload: dict, schema: dict, check_required: bool) -> list[str]:
    errors = [f"field not accepted: {k}" for k in payload if k not in schema["properties"]]
    if check_required:
        errors += [f"missing required field: {k}" for k in schema["required"] if k not in payload]
    for name, value in payload.items():
        prop = schema["properties"].get(name, {})
        expected = JSON_TYPES.get(prop.get("type"))
        if expected and value is not None and not isinstance(value, expected):
            errors.append(f"{name}: expected {prop['type']}, sent {type(value).__name__} ({value!r:.60})")
        if value is None and expected and not prop.get("nullable"):
            errors.append(f"{name}: null not allowed")
    return errors


@pytest.mark.parametrize("resource", RESOURCES)
def test_post_follows_the_schema(resource, client, mock):
    api, new, _ = RESOURCES[resource]
    factory = factory_for(client, resource)
    mock.post(factory.base_url, json={"id": 1, "result": {}})

    factory.add(new())

    assert violations(mock.last_request.json(), SPEC["schemas"][f"{api}.post"], check_required=True) == []


@pytest.mark.parametrize("resource", RESOURCES)
def test_put_follows_the_schema(resource, client, mock):
    api, _, fetched = RESOURCES[resource]
    factory = factory_for(client, resource)
    mock.get(f"{factory.base_url}9", json={"id": 9, "result": fetched})
    mock.put(f"{factory.base_url}9", json={"id": 9, "result": {}})

    factory.get(9).save()

    assert violations(mock.last_request.json(), SPEC["schemas"][f"{api}.put"], check_required=False) == []


def spec_paths_for(url: str) -> list[str]:
    """Spec paths matching the called URL (ids and slugs match the parameters)."""
    path = "/" + url.split(HOST, 1)[1].lstrip("/").split("?")[0]
    matches = []
    for candidate in SPEC["paths"]:
        pattern = re.sub(r"\\{[^}]+\\}", r"[^/]+", re.escape(candidate))
        if re.fullmatch(pattern, path):
            matches.append(candidate)
    return matches


ROUTES = [
    ("get", lambda c: c.charts.base_url), ("post", lambda c: c.charts.base_url),
    ("get", lambda c: f"{c.charts.base_url}9"), ("put", lambda c: f"{c.charts.base_url}9"),
    ("delete", lambda c: f"{c.charts.base_url}9"), ("get", lambda c: c.charts.info_url),
    ("get", lambda c: c.charts.export_url), ("post", lambda c: c.charts.import_url),
    ("get", lambda c: c.dashboards.base_url), ("post", lambda c: c.dashboards.base_url),
    ("get", lambda c: f"{c.dashboards.base_url}9"), ("put", lambda c: f"{c.dashboards.base_url}9"),
    ("get", lambda c: f"{c.dashboards.base_url}9/charts"),
    ("get", lambda c: c.datasets.base_url), ("post", lambda c: c.datasets.base_url),
    ("put", lambda c: f"{c.datasets.base_url}9"),
    ("get", lambda c: c.databases.base_url), ("post", lambda c: c.databases.base_url),
    ("put", lambda c: f"{c.databases.base_url}9"), ("post", lambda c: c.databases.test_connection_url),
    ("get", lambda c: c.saved_queries.base_url), ("post", lambda c: c.saved_queries.base_url),
    ("get", lambda c: c.assets.export_url), ("post", lambda c: c.login_endpoint),
    ("post", lambda c: c.refresh_endpoint), ("get", lambda c: c.join_urls(c.base_url, "security/csrf_token/")),
    # delete_many and Dashboards.copy
    ("delete", lambda c: c.charts.base_url), ("delete", lambda c: c.dashboards.base_url),
    ("delete", lambda c: c.datasets.base_url), ("delete", lambda c: c.saved_queries.base_url),
    ("post", lambda c: c.join_urls(c.dashboards.base_url, 9, "copy/")),
]


@pytest.mark.parametrize("method,url", ROUTES, ids=[f"{m}-{i}" for i, (m, _) in enumerate(ROUTES)])
def test_called_routes_exist_in_the_spec(method, url):
    client = SupersetClient(HOST, "robot", "password")
    called = url(client)

    paths = spec_paths_for(called)

    assert paths, f"route not found in the spec: {called}"
    assert any(method in SPEC["paths"][c] for c in paths), f"{method.upper()} does not exist in {paths}"


def test_sql_execution_uses_a_spec_route():
    client = SupersetClient(HOST, "robot", "password")

    assert spec_paths_for(client._sql_endpoint)


@pytest.mark.parametrize("resource", RESOURCES)
def test_fields_declared_in_models_are_the_spec_fields(resource):
    api, new, _ = RESOURCES[resource]
    model = type(new())

    assert set(model.POST_FIELDS) == set(SPEC["schemas"][f"{api}.post"]["properties"])
    assert set(model.PUT_FIELDS) == set(SPEC["schemas"][f"{api}.put"]["properties"])

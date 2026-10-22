"""HTTP layer: retry, errors by status, JWT refresh, multipart, SQL Lab, search and count."""
import json
import zipfile
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import requests_mock as rm

from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    NotFound,
    QueryLimitReached,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.utils.request_handler import IDEMPOTENT_METHODS, RequestHandler

HOST = "https://superset.example"
API = f"{HOST}/api/v1"


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "access-1", "refresh_token": "refresh"})
        m.get(f"{API}/security/csrf_token/", json={"result": "csrf"})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robot", "password")


def query_param(request) -> dict:
    return json.loads(parse_qs(urlparse(request.url).query)["q"][0])


# --- Retry -----------------------------------------------------------------------------------

def test_retry_only_on_idempotent_methods_without_swallowing_the_api_error():
    session = requests.Session()

    RequestHandler.configure_retries(session, retries=3, backoff_factor=0.1)

    retry = session.get_adapter("https://x").max_retries
    assert "POST" not in retry.allowed_methods and set(retry.allowed_methods) == IDEMPOTENT_METHODS
    assert retry.total == 3 and 429 in retry.status_forcelist and 503 in retry.status_forcelist
    assert retry.raise_on_status is False and retry.respect_retry_after_header is True


def test_retry_adapter_is_mounted_once_per_session():
    session = requests.Session()
    RequestHandler.configure_retries(session)
    adapter = session.get_adapter("https://x")

    RequestHandler.configure_retries(session)

    assert session.get_adapter("https://x") is adapter


# --- Errors by status ------------------------------------------------------------------------

@pytest.mark.parametrize("status,body,exception", [
    (401, {"msg": "Token has expired"}, UnauthorizedError),
    (403, {"message": "Forbidden"}, ForbiddenError),
    (404, {"message": "Not found"}, ResourceNotFoundError),
    (422, {"message": {"slice_name": ["Missing data for required field."]}}, UnprocessableEntityError),
    (400, {"message": "Bad request"}, BadRequestError),
    (400, {"errors": [{"message": "x", "error_type": "GENERIC"}]}, ComplexBadRequestError),
])
def test_api_errors_become_exceptions_by_status(status, body, exception):
    with rm.Mocker() as m:
        m.get(f"{API}/chart/1", status_code=status, json=body)
        with pytest.raises(exception) as info:
            RequestHandler.request_with_retry(f"{API}/chart/1", retries=0)

    assert info.value.response.status_code == status
    if exception is UnprocessableEntityError:
        assert info.value.message == body["message"]


def test_status_exceptions_are_still_bad_request_error():
    for exception in (UnauthorizedError, ForbiddenError, ResourceNotFoundError, UnprocessableEntityError):
        assert issubclass(exception, BadRequestError)


# --- JWT refresh -----------------------------------------------------------------------------

def test_401_refreshes_the_jwt_with_the_refresh_token_and_retries_once(client, mock):
    mock.get(f"{API}/chart/1", [{"status_code": 401, "json": {"msg": "Token has expired"}},
                                {"json": {"id": 1, "result": {}}}])
    mock.post(f"{API}/security/refresh", json={"access_token": "access-2"})

    client.get(f"{API}/chart/1")

    refresh = next(r for r in mock.request_history if r.path.endswith("/security/refresh"))
    assert refresh.headers["Authorization"] == "Bearer refresh"
    assert mock.last_request.headers["Authorization"] == "Bearer access-2"


def test_401_in_session_mode_does_not_try_to_refresh(mock):
    mock.get(f"{HOST}/login/", text='<input name="csrf_token" value="t">')
    mock.post(f"{HOST}/login/", text="ok")
    mock.get(f"{API}/chart/1", status_code=401, json={"msg": "expired"})
    client = SupersetClient(HOST, "robot", "password")
    session = requests.Session()
    session.cookies.set("session", "x", domain="superset.example")
    client._session, client._session_mode = session, True

    with pytest.raises(UnauthorizedError):
        client.get(f"{API}/chart/1")
    assert not any(r.path.endswith("/security/refresh") for r in mock.request_history)


def test_enable_session_mode_wins_even_after_session_was_accessed(client, mock, monkeypatch):
    jwt_session = client.session
    monkeypatch.setattr(type(client), "enable_session_auth", lambda self, s, u, p: s.cookies.set("session", "c"))

    client.enable_session_mode()

    assert client.session is not jwt_session


# --- Multipart, SQL Lab, search and count ---------------------------------------------------

def test_import_sends_multipart_without_json_content_type(client, mock, tmp_path):
    archive = tmp_path / "charts.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("export/metadata.yaml", "version: 1.0.0\n")
    mock.get(f"{API}/chart/_info", json={})
    mock.post(f"{API}/chart/import/", json={"message": "OK"})

    assert client.charts.import_file(archive, overwrite=True) is True

    sent = mock.last_request
    assert sent.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="formData"; filename="charts.zip"' in sent.body
    assert b'name="overwrite"' in sent.body


def test_assets_import_opens_the_given_path(client, mock, tmp_path):
    archive = tmp_path / "subdir" / "assets.zip"
    archive.parent.mkdir()
    archive.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    mock.post(f"{API}/assets/import/", json={"message": "OK"})

    assert client.assets.import_file(archive) is True
    assert b'filename="assets.zip"' in mock.last_request.body


def test_run_uses_the_api_sql_lab(client, mock):
    mock.post(f"{API}/sqllab/execute/", json={"status": "success", "columns": [{"name": "one"}], "data": [{"one": 1}]})

    columns, data = client.run(database_id=3, query="select 1 as one", query_limit=10, schema="public")

    assert mock.last_request.json() == {"database_id": 3, "sql": "select 1 as one", "runAsync": False,
                                        "queryLimit": 10, "schema": "public"}
    assert columns == [{"name": "one"}] and data == [{"one": 1}]


def test_async_run_and_limit_are_reported(client, mock):
    mock.post(f"{API}/sqllab/execute/", [{"status_code": 202, "json": {"status": "running"}},
                                          {"json": {"displayLimitReached": True, "columns": [], "data": []}}])

    with pytest.raises(NotImplementedError):
        client.run(database_id=3, query="select 1")
    with pytest.raises(QueryLimitReached):
        client.run(database_id=3, query="select 1")


def test_get_datasource_by_table_name(client, mock):
    mock.get(f"{API}/dataset/", [{"json": {"count": 1, "result": [{"id": 7, "datasource_type": "table"}]}},
                                 {"json": {"count": 0, "result": []}}])

    datasource = client.datasets.get_datasource("vw_answers")

    assert (datasource.id, datasource.type) == (7, "table")
    assert query_param(mock.last_request)["filters"] == [{"col": "table_name", "opr": "eq", "value": "vw_answers"}]
    with pytest.raises(NotFound):
        client.datasets.get_datasource("missing")


def test_count_with_filter_and_sorted_find(client, mock):
    query_filter = QueryStringFilter()
    query_filter.add("viz_type", QueryOperator.EQUAL, "pie")
    mock.get(f"{API}/chart/", json={"count": 4, "result": []})

    assert client.charts.count(query_filter) == 4
    assert query_param(mock.last_request)["filters"][0]["value"] == "pie"

    client.charts.find(query_filter, columns=["id"], order_column="changed_on", order_direction="desc")
    assert query_param(mock.last_request)["order_column"] == "changed_on"
    assert query_param(mock.last_request)["order_direction"] == "desc"


def test_find_all_walks_through_the_pages(client, mock):
    page = lambda ids: {"json": {"count": 5, "result": [{"id": i, "viz_type": "table"} for i in ids]}}  # noqa: E731
    mock.get(f"{API}/chart/", [page([1, 2]), page([3, 4]), page([5])])

    charts = client.charts.find_all(columns=["id", "viz_type"], page_size=2)

    assert [c.id for c in charts] == [1, 2, 3, 4, 5]
    assert [query_param(r)["page"] for r in mock.request_history if r.path == "/api/v1/chart/"] == [0, 1, 2]

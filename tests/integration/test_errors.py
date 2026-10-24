"""HTTP errors produced by the real Superset: exceptions by status and secrets kept out of the error logs."""
import logging
import uuid

import pytest

from supersetapiplus.databases import Database
from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)

from .conftest import PASSWORD, URL, new_client, only_test_stack, unique_name


@pytest.fixture(scope="module")
def gamma_user(client):
    """User with the Gamma role only: no permission to write databases."""
    roles = client.get(client.join_urls(URL, "api/v1/security/roles/"), params={"q": "(page_size:100)"}).json()
    gamma = next(role["id"] for role in roles["result"] if role["name"] == "Gamma")
    username, password = unique_name("gamma"), f"Gamma-{uuid.uuid4().hex}!"
    user = client.post(client.join_urls(URL, "api/v1/security/users/"), json={
        "username": username, "password": password, "first_name": "Test", "last_name": "Gamma",
        "email": f"{username}@example.com", "active": True, "roles": [gamma]}).json()
    yield username, password
    client.delete(client.join_urls(URL, "api/v1/security/users", user["id"]))


def test_unknown_field_is_400(client):
    with pytest.raises(BadRequestError) as info:
        client.post(client.charts.base_url, json={"slice_name": "x", "datasource_id": 1, "datasource_type": "table",
                                                  "unknown": 1})
    assert info.value.response.status_code == 400


def test_request_without_credentials_is_401(client):
    anonymous = new_client()
    anonymous.session.cookies.clear()

    with pytest.raises(UnauthorizedError):
        anonymous.charts.count()


@only_test_stack
def test_role_without_permission_is_403(gamma_user):
    gamma = new_client(username=gamma_user[0], password=gamma_user[1])

    with pytest.raises(ForbiddenError):
        gamma.databases.add(Database(database_name=unique_name("forbidden"), sqlalchemy_uri="sqlite://"))


def test_missing_object_is_404(client):
    with pytest.raises(ResourceNotFoundError):
        client.charts.get(2_000_000_000)
    with pytest.raises(ResourceNotFoundError):
        client.charts.delete(2_000_000_000)


def test_unknown_datasource_is_422_with_the_server_message(client):
    with pytest.raises(UnprocessableEntityError) as info:
        client.post(client.charts.base_url, json={"slice_name": "x", "datasource_id": 2_000_000_000,
                                                  "datasource_type": "table"})
    assert info.value.message == {"datasource_id": ["Datasource does not exist"]}


def test_error_list_becomes_complex_bad_request(client):
    with pytest.raises(ComplexBadRequestError):
        client.run(database_id=2_000_000_000, query="select 1")


def test_http_error_logs_do_not_expose_password_token_or_cookie(client, caplog):
    session_client, jwt_client = new_client(), new_client(session_mode=False)
    jwt_client.charts.count()
    cookie, csrf = session_client.session.cookies.get("session"), session_client.session.headers["X-CSRFToken"]
    caplog.set_level(logging.DEBUG, logger="supersetapiplus")

    with pytest.raises(UnauthorizedError):
        new_client(session_mode=False, password=f"{PASSWORD}-wrong").charts.count()
    for logged_client in (session_client, jwt_client):
        with pytest.raises(BadRequestError):
            logged_client.charts.get(2_000_000_000)

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) >= 3, "the three HTTP errors should have been logged"
    logged = caplog.text
    assert "Authorization" in logged and "Cookie" in logged, "headers are logged (masked), so the check is meaningful"
    for secret in (f"{PASSWORD}-wrong", cookie, csrf, jwt_client._access_token, jwt_client._refresh_token):
        assert secret not in logged

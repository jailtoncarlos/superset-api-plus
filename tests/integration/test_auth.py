"""Authentication against the real Superset: JWT, renewal on 401, session mode (cookie + CSRF)."""
import re
import time
import warnings

import jwt
import pytest
import requests

from supersetapiplus.auth.session import page_auth_type
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import (
    ComplexBadRequestError,
    ResourceNotFoundError,
    SessionLoginError,
    UnauthorizedError,
    UnsupportedServerVersionWarning,
)

from .conftest import LOGIN_PATH, PASSWORD, SECRET_KEY, URL, USERNAME, new_client, only_test_stack, unique_name

# The database login route for service accounts of the test stack (docker/superset/superset_config.py).
SERVICE_LOGIN_PATH = "/service-login/login/"


def write_and_delete_a_dashboard(client) -> None:
    dashboard = Dashboard(dashboard_title=unique_name("auth"))
    client.dashboards.add(dashboard)
    try:
        assert client.dashboards.delete(dashboard.id) is True
        with pytest.raises(ResourceNotFoundError):
            client.dashboards.get(dashboard.id)
    except AssertionError:
        client.dashboards.delete(dashboard.id)
        raise


def test_jwt_client_reads_and_writes_with_bearer():
    client = new_client(session_mode=False)

    assert client.charts.count() >= 0
    assert client.session.headers["Authorization"].startswith("Bearer ")
    write_and_delete_a_dashboard(client)


def test_session_mode_reads_and_writes_with_cookie_and_csrf():
    client = new_client()

    assert client.charts.count() >= 0
    assert "Authorization" not in client.session.headers
    assert "session" in client.session.cookies and client.session.headers.get("X-CSRFToken")
    write_and_delete_a_dashboard(client)


def test_expired_access_token_is_renewed_with_the_refresh_token():
    if not SECRET_KEY:
        pytest.skip("needs SUPERSET_SECRET_KEY of the server to sign an expired token")
    client = new_client(session_mode=False)
    client.charts.count()
    # The token issued by the server, re-signed with exp in the past: Superset answers 401 "Token has expired".
    # (A malformed token gets 422 from flask-jwt-extended, not 401, so it would not exercise the renewal.)
    claims = jwt.decode(client._access_token, options={"verify_signature": False})
    expired = jwt.encode({**claims, "exp": int(time.time()) - 60}, SECRET_KEY, algorithm="HS256")
    client._access_token = expired
    client.session.headers["Authorization"] = f"Bearer {expired}"
    renewals = []
    refresh = client.refresh_access_token

    def counted_refresh():
        renewals.append(1)
        refresh()

    client.refresh_access_token = counted_refresh

    assert client.charts.count() >= 0
    assert renewals == [1] and client._access_token != expired


def test_malformed_access_token_is_renewed_with_the_refresh_token():
    # Superset (flask-jwt-extended) answers 422 {"msg": "Not enough segments"}, not 401, for a malformed token.
    client = new_client(session_mode=False)
    client.charts.count()
    client._access_token = "malformed"
    client.session.headers["Authorization"] = "Bearer malformed"

    assert client.charts.count() >= 0
    assert client._access_token != "malformed"


def test_jwt_error_message_reaches_the_exception():
    client = new_client(session_mode=False)
    client.charts.count()
    client._refresh_token = None  # no renewal: the server's explanation must reach the caller
    client.session.headers["Authorization"] = "Bearer malformed"

    with pytest.raises(UnauthorizedError) as info:
        client.charts.count()
    assert info.value.message == "Not enough segments"


def count_requests(session, path: str) -> list[int]:
    """Spy (not an HTTP mock): status of every response of `session` to a URL containing `path`."""
    statuses: list[int] = []
    session.hooks["response"].append(lambda r, *args, **kwargs: statuses.append(r.status_code)
                                     if path in r.url else None)
    return statuses


def test_lost_session_logs_in_again_once_without_trying_the_jwt_refresh(monkeypatch):
    client = new_client()
    client.session.cookies.clear()  # expired or lost session cookie: GET 401, POST 400 "CSRF session token"
    attempts = []
    monkeypatch.setattr(client, "refresh_access_token", lambda: attempts.append(1))

    assert client.charts.count() >= 0
    client.session.cookies.clear()
    write_and_delete_a_dashboard(client)
    assert attempts == []


@pytest.mark.parametrize("session_mode", [True, False])
def test_rejected_csrf_token_is_renewed_and_the_write_repeated_once(session_mode):
    client = new_client(session_mode=session_mode)
    client.session.headers["X-CSRFToken"] = "expired-token"  # 400 "The CSRF token is invalid."
    statuses = count_requests(client.session, "/api/v1/dashboard/")

    write_and_delete_a_dashboard(client)

    assert client.session.headers["X-CSRFToken"] != "expired-token"
    assert statuses[:2] == [400, 201]


def test_credentials_are_renewed_at_most_once_per_request(monkeypatch):
    client = new_client()
    session = client.session
    session.headers["X-CSRFToken"] = "expired-token"
    statuses = count_requests(session, "/api/v1/dashboard/")
    renewals = []
    # The renewal "succeeds" without fixing the token: the second rejection must be raised, not retried.
    monkeypatch.setattr(client, "_renew_credentials", lambda error: renewals.append(error) or True)

    with pytest.raises(ComplexBadRequestError, match="The CSRF token is invalid"):
        client.dashboards.add(Dashboard(dashboard_title=unique_name("auth")))
    assert (len(renewals), statuses) == (1, [400, 400])


def test_enable_session_mode_wins_after_the_jwt_session_was_used():
    client = new_client(session_mode=False)
    jwt_session = client.session
    client.charts.count()

    client.enable_session_mode(LOGIN_PATH)

    assert client.session is not jwt_session and "Authorization" not in client.session.headers
    write_and_delete_a_dashboard(client)


@only_test_stack  # the service route exists in the test stack configuration
def test_session_mode_logs_in_through_another_login_path_and_keeps_it_for_new_logins():
    client = SupersetClient(URL, USERNAME, PASSWORD, verify=URL.startswith("https"))
    paths = []
    login = client.enable_session_auth

    def recorded_login(session, username, password, login_path="/login/"):
        paths.append(login_path)
        login(session, username, password, login_path)

    client.enable_session_auth = recorded_login
    client.enable_session_mode(login_path=SERVICE_LOGIN_PATH)
    write_and_delete_a_dashboard(client)

    client.session.cookies.clear()  # lost session: the 401 logs in again, through the same route
    assert client.charts.count() >= 0
    assert paths == [SERVICE_LOGIN_PATH, SERVICE_LOGIN_PATH]


def test_session_mode_says_when_superset_refuses_the_password():
    client = SupersetClient(URL, USERNAME, f"{PASSWORD}-wrong", verify=URL.startswith("https"))

    with pytest.raises(SessionLoginError, match="refused the session login"):
        client.enable_session_mode(LOGIN_PATH)


def test_session_mode_explains_a_login_page_without_a_password_form():
    """On an instance whose people log in through OAuth, /login/ lists the providers and does not take a POST."""
    page = requests.get(f"{URL}/login/", headers={"Accept": "text/html"}, verify=URL.startswith("https")).text
    if page_auth_type(page) in (None, 1, 2):
        pytest.skip("the instance logs in through a password form (run the stack with SUPERSET_TEST_AUTH_TYPE=oauth)")
    client = SupersetClient(URL, USERNAME, PASSWORD, verify=URL.startswith("https"))

    with pytest.raises(SessionLoginError, match="AUTH_OAUTH.*login_path") as error:
        client.enable_session_mode()
    assert error.value.auth_type == 4


def test_the_server_version_is_read_once_and_another_major_version_is_reported():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = new_client(session_mode=False)
        client.charts.count()
        client.enable_session_mode(LOGIN_PATH)  # a second login does not warn again

    version = client.server_version
    assert re.match(r"\d+\.\d+", version), version
    reported = [w for w in caught if issubclass(w.category, UnsupportedServerVersionWarning)]
    if version.startswith("7."):
        assert reported == []
    else:  # the 6.1 stack until the test stack moves to 7.0
        assert len(reported) == 1 and version in str(reported[0].message)

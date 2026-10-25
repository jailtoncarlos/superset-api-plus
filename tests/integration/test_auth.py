"""Authentication against the real Superset: JWT, renewal on 401, session mode (cookie + CSRF)."""
import time

import jwt
import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import ComplexBadRequestError, ResourceNotFoundError, UnauthorizedError

from .conftest import SECRET_KEY, new_client, unique_name


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

    client.enable_session_mode()

    assert client.session is not jwt_session and "Authorization" not in client.session.headers
    write_and_delete_a_dashboard(client)

"""HTTP layer pieces the real Superset cannot exercise deterministically.

Server behavior (errors by status, JWT renewal, session mode, multipart, SQL Lab, search) is tested against
the real Superset in tests/integration. What stays here, and why:
- retry policy and adapter mounting: the server does not produce 5xx/429 on demand (429 comes from the
  rate limit of a production-mode Superset, reached by bursts; the policy is checked without HTTP);
- exception hierarchy: no server involved;
- asynchronous SQL Lab (202): the test stack has no Celery workers to run queries asynchronously;
- status mapping of error bodies: built responses, no HTTP (the real 403 is in tests/integration/test_errors.py).
"""
import json

import pytest
import requests
import requests_mock as rm

from supersetapiplus.client import SupersetClient
from supersetapiplus.core.types import ErrorLevel, SupersetErrorType
from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from supersetapiplus.transport.http import IDEMPOTENT_METHODS, RequestHandler

HOST = "https://superset.example"
API = f"{HOST}/api/v1"


def test_retry_only_on_idempotent_methods_without_swallowing_the_api_error():
    session = requests.Session()

    RequestHandler.configure_retries(session, retries=3, backoff_factor=0.1)

    retry = session.get_adapter("https://x").max_retries
    assert "POST" not in retry.allowed_methods and set(retry.allowed_methods) == IDEMPOTENT_METHODS
    assert retry.total == 3 and 429 in retry.status_forcelist and 503 in retry.status_forcelist
    assert retry.raise_on_status is False and retry.respect_retry_after_header is True


def test_any_method_is_retried_on_429_and_only_idempotent_ones_on_server_errors():
    # The real stack produced it: the suite exceeded RATELIMIT_APPLICATION (50/s) and the login POST got 429.
    session = requests.Session()
    RequestHandler.configure_retries(session, retries=3)
    retry = session.get_adapter("https://x").max_retries

    assert retry.is_retry("POST", 429) and retry.is_retry("GET", 429)
    assert retry.is_retry("GET", 503) and not retry.is_retry("POST", 503)
    assert not retry.new(total=0).is_retry("POST", 429), "stops when the retries are exhausted"


def test_retry_adapter_is_mounted_once_per_session():
    session = requests.Session()
    RequestHandler.configure_retries(session)
    adapter = session.get_adapter("https://x")

    RequestHandler.configure_retries(session)

    assert session.get_adapter("https://x") is adapter


def test_status_exceptions_are_still_bad_request_error():
    for exception in (UnauthorizedError, ForbiddenError, ResourceNotFoundError, UnprocessableEntityError):
        assert issubclass(exception, BadRequestError)


def test_async_sql_lab_run_is_reported_as_not_supported():
    with rm.Mocker() as mock:
        mock.post(f"{API}/security/login", json={"access_token": "access", "refresh_token": "refresh"})
        mock.get(f"{API}/security/csrf_token/", json={"result": "csrf"})
        mock.post(f"{API}/sqllab/execute/", status_code=202, json={"status": "running"})

        with pytest.raises(NotImplementedError):
            SupersetClient(HOST, "robot", "password").run(database_id=3, query="select 1")


def response(status: int, body: dict) -> requests.Response:
    """A Superset error response as received (no HTTP involved: raise_for_status only reads it)."""
    built = requests.Response()
    built.status_code, built._content = status, json.dumps(body).encode()
    built.headers["Content-Type"] = "application/json"
    built.request = requests.Request("GET", f"{API}/chart/1").prepare()
    built.url = built.request.url
    return built


SIP40 = {"errors": [{"message": "Denied", "error_type": "DATASOURCE_SECURITY_ACCESS_ERROR", "level": "error"}]}


@pytest.mark.parametrize("status,exception", [(401, UnauthorizedError), (403, ForbiddenError),
                                              (404, ResourceNotFoundError), (422, UnprocessableEntityError)])
def test_error_list_body_is_mapped_by_status(status, exception):
    with pytest.raises(exception) as info:
        RequestHandler.raise_for_status(response(status, SIP40))
    assert info.value.errors == SIP40["errors"]


def test_error_list_with_another_status_is_a_complex_bad_request_error():
    with pytest.raises(ComplexBadRequestError) as info:
        RequestHandler.raise_for_status(response(500, SIP40))
    assert isinstance(info.value, BadRequestError) and info.value.errors == SIP40["errors"]


def test_sip40_errors_are_typed_and_readable():
    # Body measured on Superset 6.1.0 for a POST with an invalid CSRF token; a second error with a type and a
    # level this library does not know (a newer Superset) is kept as text.
    body = {"errors": [
        {"message": "400 Bad Request: The CSRF token is invalid.", "error_type": "GENERIC_BACKEND_ERROR",
         "level": "error", "extra": {"issue_codes": [
             {"code": 1011, "message": "Issue 1011 - Superset encountered an unexpected error."}]}},
        {"message": "Other", "error_type": "SOME_NEW_ERROR", "level": "notice"},
    ]}
    with pytest.raises(ComplexBadRequestError) as info:
        RequestHandler.raise_for_status(response(400, body))

    first, second = info.value.superset_errors
    assert (first.error_type, first.level) == (SupersetErrorType.GENERIC_BACKEND_ERROR, ErrorLevel.ERROR)
    assert [issue["code"] for issue in first.issue_codes] == [1011]
    assert (second.error_type, second.level, second.issue_codes) == ("SOME_NEW_ERROR", "notice", [])
    assert str(info.value) == (
        "400 Bad Request: The CSRF token is invalid. (GENERIC_BACKEND_ERROR) "
        "[Issue 1011 - Superset encountered an unexpected error.]\nOther (SOME_NEW_ERROR)")


@pytest.mark.parametrize("status,msg", [(401, "Token has expired"), (422, "Not enough segments"),
                                        (422, "Only non-refresh tokens are allowed")])
def test_token_rejected_by_flask_jwt_extended_is_unauthorized_with_its_message(status, msg):
    # Formats measured on Superset 6.1.0: flask-jwt-extended answers {"msg": ...}, with 422 for a bad token.
    with pytest.raises(UnauthorizedError) as info:
        RequestHandler.raise_for_status(response(status, {"msg": msg}))
    assert info.value.message == msg and msg in str(info.value)


def test_validation_422_with_message_stays_unprocessable():
    with pytest.raises(UnprocessableEntityError):
        RequestHandler.raise_for_status(response(422, {"message": {"datasource_id": ["Datasource does not exist"]}}))

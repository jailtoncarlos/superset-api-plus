"""HTTP layer pieces the real Superset cannot exercise deterministically.

Server behavior (errors by status, JWT renewal, session mode, multipart, SQL Lab, search) is tested against
the real Superset in tests/integration. What stays here, and why:
- retry policy and adapter mounting: the server does not produce 5xx/429 on demand;
- exception hierarchy: no server involved;
- asynchronous SQL Lab (202): the test stack has no Celery workers to run queries asynchronously.
"""
import pytest
import requests
import requests_mock as rm

from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import (
    BadRequestError,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from supersetapiplus.utils.request_handler import IDEMPOTENT_METHODS, RequestHandler

HOST = "https://superset.example"
API = f"{HOST}/api/v1"


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

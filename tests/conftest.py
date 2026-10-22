"""Shared fixtures and integration test configuration."""
import json
import os
from pathlib import Path

import pytest
import requests_mock  # noqa

from supersetapiplus.client import SupersetClient

ROOT = Path(__file__).parent.parent
API_MOCKS = Path(__file__).parent / "mocks" / "endpoints"

# Fake address used only by the HTTP mocks.
SUPERSET_BASE_URI = "https://superset.mock"
SUPERSET_API_URI = f"{SUPERSET_BASE_URI}/api/v1"


def load_env_file(path: Path = ROOT / ".env") -> None:
    """Load the test stack .env into the environment without overriding variables already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


load_env_file()


@pytest.fixture
def permanent_requests(requests_mock):  # noqa
    # Register each tests/mocks/endpoints/<resource>/<endpoint>.<method> file as a response.
    for domain in API_MOCKS.iterdir():
        if domain.is_dir():
            for endpoint in domain.iterdir():
                if endpoint.is_file():
                    endpoint_name, action = endpoint.name.split(".")
                    url = f"{SUPERSET_API_URI}/{domain.name}/{endpoint_name}"
                    getattr(requests_mock, action)(url=url, json=json.load(endpoint.open()))
                    getattr(requests_mock, action)(url=f"{url}/", json=json.load(endpoint.open()))


@pytest.fixture
def client(permanent_requests):
    yield SupersetClient(SUPERSET_BASE_URI, "test", "test")

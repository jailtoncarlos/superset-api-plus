"""Client security: application logging, TLS verification and the masking of secrets.

The secrets in real error logs are checked against the real Superset (tests/integration/test_errors.py).
TLS verification stays mocked: the test stack serves plain HTTP, so `verify` cannot be observed on it.
Multipart error logging uses a prepared request and a built response without HTTP: the contract under
test is that the local logger never emits the uploaded content, regardless of the server's response.
"""
import json
import os
import subprocess
import sys

import pytest
import requests
import requests_mock
import yaml

from supersetapiplus.client import SupersetClient
from supersetapiplus.transport.http import RequestHandler
from supersetapiplus.core.masking import MASK, mask_body, mask_data, mask_headers, mask_request_kwargs

HOST = "https://superset.example"
PASSWORD = "s3cr3t-top-secret"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.access-token"


def client_with_session(verify: bool) -> SupersetClient:
    client = SupersetClient(HOST, username="robot", password=PASSWORD, verify=verify)
    client._session = requests.Session()  # avoids the real login
    return client


def test_importing_the_package_does_not_configure_application_logging():
    code = "import logging, supersetapiplus; print(len(logging.getLogger().handlers))"
    output = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert output.stdout.strip() == "0"


@pytest.mark.parametrize("verify", [True, False])
@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
def test_client_http_methods_honor_verify(method, verify):
    client = client_with_session(verify)
    url = f"{HOST}/api/v1/chart/1"

    with requests_mock.Mocker() as mock:
        getattr(mock, method)(url, json={"result": {}})
        getattr(client, method)(url)

    assert mock.last_request.verify is verify


def test_request_without_explicit_verify_inherits_the_session():
    session = requests.Session()
    session.verify = True

    with requests_mock.Mocker() as mock:
        mock.get(f"{HOST}/api/v1/me/", json={})
        RequestHandler.request_with_retry(f"{HOST}/api/v1/me/", session=session)

    assert mock.last_request.verify is True


def test_masks_sensitive_headers_without_changing_the_others():
    headers = {"Authorization": "Bearer x", "Cookie": "a=b", "X-CSRFToken": "c", "Accept": "application/json"}

    assert mask_headers(headers) == {"Authorization": MASK, "Cookie": MASK, "X-CSRFToken": MASK,
                                     "Accept": "application/json"}
    assert headers["Authorization"] == "Bearer x"


def test_masks_json_body_form_body_and_connection_uri():
    json_body = json.dumps({"username": "robot", "password": PASSWORD, "nested": {"refresh_token": "r"}})
    form_body = f"csrf_token=abc&username=robot&password={PASSWORD}"
    database = {"database_name": "dw", "sqlalchemy_uri": f"postgresql://robot:{PASSWORD}@db:5432/dw"}

    assert json.loads(mask_body(json_body)) == {"username": "robot", "password": MASK, "nested": {"refresh_token": MASK}}
    assert mask_body(form_body) == f"csrf_token={MASK.replace('*', '%2A')}&username=robot&password={MASK.replace('*', '%2A')}"
    assert mask_data(database)["sqlalchemy_uri"] == f"postgresql://robot:{MASK}@db:5432/dw"


@pytest.mark.parametrize("field", ["ssh_tunnel_private_keys", "ssh_tunnel_private_key_passwords"])
def test_masks_json_encoded_ssh_import_secrets_without_changing_request_data(field):
    secret = json.dumps({"databases/examples.yaml": "synthetic-ssh-secret"})
    kwargs = {"data": {"overwrite": "false", field: secret}}

    assert mask_request_kwargs(kwargs) == {"data": {"overwrite": "false", field: MASK}}
    assert kwargs == {"data": {"overwrite": "false", field: secret}}


@pytest.mark.parametrize("content_type", ["multipart/form-data", "Multipart/Form-Data"])
def test_multipart_import_error_logs_omit_credentials_and_uploaded_content(caplog, content_type):
    secrets = {
        "ssh_tunnel_passwords": "synthetic-tunnel-password",
        "ssh_tunnel_private_keys": "-----BEGIN PRIVATE KEY-----\nsynthetic-private-key\n-----END PRIVATE KEY-----",
        "ssh_tunnel_private_key_passwords": "synthetic-key-passphrase",
    }
    uploaded_content = b"synthetic-private-archive-content"
    request = requests.Request(
        "POST", f"{HOST}/api/v1/dashboard/import/",
        data={field: json.dumps({"databases/examples.yaml": secret}) for field, secret in secrets.items()},
        files={"formData": ("bundle.zip", uploaded_content, "application/zip")},
    ).prepare()
    boundary = request.headers["Content-Type"].split(";", 1)[1]
    request.headers["Content-Type"] = f"{content_type};{boundary}"
    original_body = request.body
    response = requests.Response()
    response.status_code, response._content = 400, b'{"message": "Import rejected"}'
    response.headers["Content-Type"] = "application/json"
    response.request, response.url = request, request.url

    with caplog.at_level("ERROR", logger="supersetapiplus.transport.http"):
        with pytest.raises(requests.HTTPError):
            RequestHandler.raise_for_status(response)

    for secret in ("synthetic-tunnel-password", "synthetic-private-key", "synthetic-key-passphrase"):
        assert secret not in caplog.text
    assert uploaded_content.decode() not in caplog.text
    assert "Request Method: POST" in caplog.text
    assert request.url in caplog.text
    assert "Response Status Code: 400" in caplog.text
    assert "Import rejected" in caplog.text
    assert request.body == original_body


def test_network_parameters_come_from_the_environment():
    code = ("from supersetapiplus.transport import http as r; "
              "print(r.TIMEOUT_CONNECT, r.TIMEOUT_READ, r.DEFAULT_RETRIES, r.DEFAULT_BACKOFF_FACTOR)")
    env = {**os.environ, "SUPERSET_API_PLUS_TIMEOUT_READ": "60", "SUPERSET_API_PLUS_RETRIES": "5",
                "SUPERSET_API_PLUS_BACKOFF_FACTOR": "1.5"}
    env.pop("SUPERSET_API_PLUS_TIMEOUT_CONNECT", None)

    output = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env)

    assert output.stdout.split() == ["10", "60", "5", "1.5"]


def test_yaml_export_is_parsed_with_safe_load(tmp_path, monkeypatch):
    # An export body with a Python tag must not be resolved: FullLoader returns os.system for this one.
    client = SupersetClient(HOST, username="robot", password=PASSWORD)
    body = requests.Response()
    body.status_code, body._content = 200, b"payload: !!python/name:os.system\n"
    body.headers["content-type"] = "application/text"
    monkeypatch.setattr(client, "get", lambda *args, **kwargs: body)

    with pytest.raises(yaml.constructor.ConstructorError):
        client.charts.export([1], tmp_path / "export.yaml")


def test_import_sends_ssh_tunnel_secrets_by_database_file(tmp_path, monkeypatch):
    client = SupersetClient(HOST, username="robot", password=PASSWORD)
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"zip")
    sent = {}

    def capture(url, **kwargs):
        sent.update(kwargs["data"])
        reply = requests.Response()
        reply.status_code, reply._content = 200, b'{"message": "OK"}'
        return reply

    monkeypatch.setattr(client, "post", capture)
    client.dashboards.import_file(archive, ssh_tunnel_passwords={"examples": "tunnel-secret"})

    assert json.loads(sent["ssh_tunnel_passwords"]) == {"databases/examples.yaml": "tunnel-secret"}
    assert "ssh_tunnel_private_keys" not in sent


def test_login_without_credentials_raises_instead_of_prompting():
    from supersetapiplus.exceptions import MissingCredentialsError

    client = SupersetClient(HOST, username="robot", password=None)
    with pytest.raises(MissingCredentialsError):
        client.authenticate(requests.Session())
    with pytest.raises(MissingCredentialsError):
        client.enable_session_mode()

"""Local multipart serialization across a credential renewal, without HTTP.

Prepared requests consume the streams exactly as requests does. The injected rejection only triggers
the local replay path; Superset's authentication and import behavior is tested in tests/integration.
"""
from io import BytesIO

import pytest
import requests

from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import UnauthorizedError
from supersetapiplus.transport.http import RequestHandler


@pytest.mark.parametrize("as_mapping", [True, False])
@pytest.mark.parametrize("file_format", ["bare", "pair", "triple", "headers"])
def test_authenticated_replay_preserves_file_offsets_and_literal_parts(monkeypatch, as_mapping, file_format):
    stream = BytesIO(b"skip-prefix:archive-content")
    stream.seek(len(b"skip-prefix:"))
    other = BytesIO(b"second-file-content")
    part = {
        "bare": stream,
        "pair": ("archive.zip", stream),
        "triple": ("archive.zip", stream, "application/zip"),
        "headers": ("archive.zip", stream, "application/zip", {"X-Part": "custom"}),
    }[file_format]
    parts = [("formData", part), ("other", other), ("passwords", (None, "{}")), ("literal", b"literal-content")]
    files = dict(parts) if as_mapping else parts
    client = SupersetClient("https://superset.example")
    client._session = requests.Session()
    bodies = []
    renewals = []

    def prepare(url, method, session, **kwargs):
        bodies.append(requests.Request(method, url, files=kwargs["files"]).prepare().body)
        if len(bodies) == 1:
            raise UnauthorizedError("Token has expired")
        response = requests.Response()
        response.status_code = 200
        return response

    monkeypatch.setattr(RequestHandler, "request_with_retry", prepare)
    monkeypatch.setattr(client, "_renew_credentials", lambda error: renewals.append(error) or True)

    assert client.post("https://superset.example/api/v1/chart/import/", files=files).status_code == 200
    assert len(bodies) == 2 and len(renewals) == 1
    for body in bodies:
        assert b"archive-content" in body and b"skip-prefix:" not in body
        assert b"second-file-content" in body and b"literal-content" in body and b"{}" in body


@pytest.mark.parametrize("broken_operation", ["tell", "seek"])
@pytest.mark.parametrize("rejected", [True, False])
def test_unrewindable_file_is_allowed_once_but_never_replayed_empty(monkeypatch, broken_operation, rejected):
    stream = BytesIO(b"archive-content")
    client = SupersetClient("https://superset.example")
    client._session = requests.Session()
    bodies = []

    def unsupported(*args):
        raise OSError("Stream cannot rewind")

    def prepare(url, method, session, **kwargs):
        bodies.append(requests.Request(method, url, files=kwargs["files"]).prepare().body)
        if rejected:
            raise UnauthorizedError("Token has expired")
        response = requests.Response()
        response.status_code = 200
        return response

    monkeypatch.setattr(stream, broken_operation, unsupported)
    monkeypatch.setattr(RequestHandler, "request_with_retry", prepare)
    monkeypatch.setattr(client, "_renew_credentials", lambda error: True)

    if rejected:
        with pytest.raises(requests.exceptions.UnrewindableBodyError):
            client.post("https://superset.example/api/v1/chart/import/", files={"formData": stream})
    else:
        assert client.post("https://superset.example/api/v1/chart/import/", files={"formData": stream}).status_code == 200
    assert len(bodies) == 1 and b"archive-content" in bodies[0]

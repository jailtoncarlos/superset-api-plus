"""The version check of the integration fixtures (tests/integration/server_version.py): pure logic, no HTTP.

`SupersetClient.server_version` is None when `/version` is unavailable; the fixtures must not fail on it."""
from types import SimpleNamespace

import pytest

from tests.integration.server_version import is_superset_7, server_major


@pytest.mark.parametrize(("version", "major"), [("7.0.0rc3", 7), ("6.1.0", 6), ("10.2.1", 10), (None, None),
                                                ("", None), ("unknown", None)])
def test_the_major_version_is_read_or_unknown(version, major):
    assert server_major(version) == major


@pytest.mark.parametrize(("version", "expected"), [("7.0.0rc3", True), ("8.0.0", True), ("6.1.0", False),
                                                   (None, False)])
def test_an_unknown_server_version_is_handled_as_before_7(version, expected):
    assert is_superset_7(SimpleNamespace(server_version=version)) is expected

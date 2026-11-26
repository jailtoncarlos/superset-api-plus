"""Major version of the Superset under test, for the tests and fixtures that differ on Superset 7.0.

`SupersetClient.server_version` is best-effort: it is None when `/version` is unavailable or fails. An unknown version
is handled as a server before 7.0 (no 7.0 xfails, no purge of archived objects, the 7.0-only tests skipped) instead of
breaking the setup or the teardown."""
from supersetapiplus.client import SupersetClient


def server_major(version: str | None) -> int | None:
    """The major version of a version string such as "7.0.0rc3", or None when it is unknown."""
    head = (version or "").split(".")[0]
    return int(head) if head.isdigit() else None


def is_superset_7(client: SupersetClient) -> bool:
    """True when the server is known to be Superset 7.0 or later."""
    major = server_major(client.server_version)
    return major is not None and major >= 7

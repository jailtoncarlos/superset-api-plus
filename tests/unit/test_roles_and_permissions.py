"""Roles and permissions: the two shapes of a permission read from Superset and its display name.

That the server accepts the requests is tested in tests/integration/test_roles.py; the payloads are checked
against the specification in test_openapi_conformance.py.
"""
import pytest

from supersetapiplus.client import SupersetClient
from supersetapiplus.resources.security import Permission


@pytest.mark.parametrize("data", [
    {"id": 7, "permission": {"name": "can_read"}, "view_menu": {"name": "Chart"}},  # permissions-resources/
    {"id": 7, "permission_name": "can_read", "view_menu_name": "Chart"},  # roles/{id}/permissions/
])
def test_permission_read_from_either_endpoint_has_the_fab_display_name(data):
    permission = Permission.from_json(data)

    assert (permission.id, permission.permission_name, permission.view_menu_name) == (7, "can_read", "Chart")
    assert permission.display_name == "can read on Chart"


def test_display_name_keeps_the_view_menu_as_is():
    permission = Permission(id=1, permission_name="all_datasource_access", view_menu_name="all_datasource_access")

    assert permission.display_name == "all datasource access on all_datasource_access"


def test_a_permission_without_id_is_not_granted():
    client = SupersetClient("https://superset.example", "robot", "password")

    with pytest.raises(ValueError, match="without id"):
        client.roles.set_permissions(9, [Permission(permission_name="can_read", view_menu_name="Chart")])

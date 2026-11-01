"""Roles and permissions through the Flask-AppBuilder security API (client.roles, client.permissions)."""
import pytest

from supersetapiplus.exceptions import NotFound
from supersetapiplus.resources.security import Role

from .conftest import name_filter, only_test_stack, unique_name

pytestmark = only_test_stack  # changes the security of the instance


def test_role_created_found_by_name_renamed_and_removed(client, cleanup):
    role = Role(name=unique_name("role"))
    cleanup.role(client.roles.add(role))

    found = client.roles.find_one(name_filter("name", role.name))
    assert found.id == role.id
    found.name = unique_name("renamed")
    found.save()
    assert client.roles.get(role.id).name == found.name

    assert client.roles.delete(role.id)
    with pytest.raises(NotFound):
        client.roles.find_one(name_filter("name", found.name))


def test_permissions_listed_across_pages_with_the_display_name(client):
    permissions = client.permissions.find_all(page_size=50)

    assert len(permissions) == client.permissions.count() > 50
    assert len({p.id for p in permissions}) == len(permissions)
    assert "can read on Chart" in {p.display_name for p in permissions}


def test_role_permissions_are_replaced_by_display_name(client, cleanup):
    role = Role(name=unique_name("role"))
    cleanup.role(client.roles.add(role))
    names = ["can read on Chart", "can read on Dashboard", "can read on Dataset"]

    role.set_permissions(client.permissions.find_by_display_names(names))
    assert sorted(p.display_name for p in role.permissions()) == sorted(names)

    client.roles.set_permissions(role.id, client.permissions.find_by_display_names(names[:1]))
    assert [p.display_name for p in client.roles.permissions(role.id)] == names[:1]


def test_unknown_permission_names_are_all_reported(client):
    with pytest.raises(NotFound, match="can fly on Chart, can read on Nothing"):
        client.permissions.find_by_display_names(["can read on Chart", "can fly on Chart", "can read on Nothing"])

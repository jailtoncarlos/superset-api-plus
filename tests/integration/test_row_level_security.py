"""Row level security rules (client.row_level_security): CRUD, create or update by name, and the clause applied to
the data a role sees."""
import uuid

import pytest

from supersetapiplus.core.types import RowLevelSecurityFilterType
from supersetapiplus.exceptions import BadRequestError, NotFound, ResourceNotFoundError
from supersetapiplus.resources.row_level_security import RowLevelSecurityRule
from supersetapiplus.resources.security import Role

from .conftest import URL, name_filter, new_client, only_test_stack, unique_name

pytestmark = only_test_stack  # changes the security of the instance and creates a user


@pytest.fixture
def restricted_user(client, cleanup):
    """A role of its own (the one the rules name) and a user with it; Admin too, so it may query the dataset."""
    role = Role(name=unique_name("rls"))
    cleanup.role(client.roles.add(role))
    admin = client.roles.find_one(name_filter("name", "Admin"))
    username, password = unique_name("rls"), f"Rls-{uuid.uuid4().hex}!"
    user = client.post(client.join_urls(URL, "api/v1/security/users/"), json={
        "username": username, "password": password, "first_name": "Test", "last_name": "Rls",
        "email": f"{username}@example.com", "active": True, "roles": [admin.id, role.id]}).json()
    yield role, new_client(username=username, password=password)
    client.delete(client.join_urls(URL, "api/v1/security/users", user["id"]))


def campuses(client, chart) -> list[str]:
    """The campuses of the chart data as `client`'s user sees them (cache bypassed)."""
    query_context = {**chart.ui_query_context(), "force": True}
    result = client.post(client.join_urls(client.charts.base_url, "data"), json=query_context).json()["result"]
    return sorted(row["campus"] for row in result[0]["data"])


def test_rule_created_read_updated_and_removed(client, cleanup, dataset, restricted_user):
    role, _ = restricted_user
    rule = RowLevelSecurityRule(name=unique_name("rule"), filter_type=RowLevelSecurityFilterType.REGULAR,
                                tables=[dataset], roles=[role], clause="campus <> 'South'", group_key="campus")
    cleanup.rls_rule(client.row_level_security.add(rule))

    found = client.row_level_security.find_one(name_filter("name", rule.name))
    assert found.id == rule.id and found.filter_type == RowLevelSecurityFilterType.REGULAR
    assert [t["id"] for t in found.tables] == [dataset.id] and [r["id"] for r in found.roles] == [role.id]
    assert (found.clause, found.group_key) == ("campus <> 'South'", "campus")

    found.filter_type, found.description = RowLevelSecurityFilterType.BASE, "every role but this one"
    found.save()
    saved = client.row_level_security.get(rule.id)
    assert (saved.filter_type, saved.description) == (RowLevelSecurityFilterType.BASE, "every role but this one")
    assert [t["id"] for t in saved.tables] == [dataset.id], "a save keeps the tables read"

    assert client.row_level_security.delete(rule.id)
    with pytest.raises((NotFound, ResourceNotFoundError)):
        client.row_level_security.get(rule.id)


def test_the_clause_filters_the_data_of_the_role(client, cleanup, dataset, add_chart, restricted_user):
    role, restricted = restricted_user
    chart = add_chart()
    rule = RowLevelSecurityRule(name=unique_name("rule"), filter_type=RowLevelSecurityFilterType.REGULAR,
                                tables=[dataset.id], roles=[role.id], clause="campus <> 'South'")
    cleanup.rls_rule(client.row_level_security.add(rule))

    assert campuses(restricted, chart) == ["North"]
    assert campuses(client, chart) == ["North", "South"], "users without the role are not filtered"

    rule.clause = "campus <> 'North'"
    rule.save()
    assert campuses(restricted, chart) == ["South"]


def test_create_or_update_by_name_is_idempotent(client, cleanup, dataset, restricted_user):
    role, _ = restricted_user
    name = unique_name("rule")

    def declared(clause: str) -> RowLevelSecurityRule:
        return RowLevelSecurityRule(name=name, filter_type=RowLevelSecurityFilterType.REGULAR, tables=[dataset],
                                    roles=[role], clause=clause, description="declared in code")

    rule_id = cleanup.rls_rule(client.row_level_security.create_or_update(declared("campus <> 'South'")))
    assert client.row_level_security.create_or_update(declared("campus <> 'South'")) == rule_id, "same rule again"
    assert client.row_level_security.create_or_update(declared("campus <> 'North'")) == rule_id, "updated in place"

    assert client.row_level_security.count(name_filter("name", name)) == 1
    saved = client.row_level_security.get(rule_id)
    assert (saved.clause, saved.description) == ("campus <> 'North'", "declared in code")
    assert [t["id"] for t in saved.tables] == [dataset.id] and [r["id"] for r in saved.roles] == [role.id]


def test_create_or_update_matches_the_whole_name(client, cleanup, dataset, restricted_user):
    role, _ = restricted_user
    name = unique_name("rule")
    longer = RowLevelSecurityRule(name=f"{name}-longer", filter_type=RowLevelSecurityFilterType.BASE,
                                  tables=[dataset], roles=[role], clause="1 = 1")
    cleanup.rls_rule(client.row_level_security.add(longer))

    rule = RowLevelSecurityRule(name=name, filter_type=RowLevelSecurityFilterType.BASE, tables=[dataset],
                                roles=[role], clause="1 = 1")
    cleanup.rls_rule(client.row_level_security.create_or_update(rule))

    assert rule.id != longer.id and client.row_level_security.get(longer.id).name == f"{name}-longer"


def test_superset_keeps_rule_names_unique(client, cleanup, dataset):
    """create_or_update looks a rule up by name: the server must refuse a second rule with the same name."""
    def rule() -> RowLevelSecurityRule:
        return RowLevelSecurityRule(name=name, filter_type=RowLevelSecurityFilterType.BASE, tables=[dataset],
                                    clause="1 = 1")

    name = unique_name("rule")
    cleanup.rls_rule(client.row_level_security.add(rule()))
    with pytest.raises(BadRequestError):
        cleanup.rls_rule(client.row_level_security.add(rule()))

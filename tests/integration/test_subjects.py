"""Subjects of Superset 7.0 (client.subjects): the principal that editors, viewers and row level security rules refer
to. Read-only; skipped on a server before 7.0, which has no subjects."""
import pytest

from supersetapiplus.core.types import SubjectType
from supersetapiplus.exceptions import NotFound
from supersetapiplus.resources.security import Role, Subject

from .conftest import only_test_stack, unique_name
from .server_version import is_superset_7

pytestmark = only_test_stack  # creates a role


@pytest.fixture
def superset_7(client):
    if not is_superset_7(client):
        pytest.skip(f"Superset {client.server_version or '(unknown version)'} has no subjects (7.0)")


def test_a_created_role_has_a_subject(client, cleanup, superset_7):
    role = Role(name=unique_name("role"))
    cleanup.role(client.roles.add(role))

    subject = client.subjects.for_role(role.id)

    assert isinstance(subject, Subject)
    assert (subject.type, subject.role_id, subject.label) == (SubjectType.ROLE, role.id, role.name)
    assert subject.user_id is None and subject.group_id is None
    assert client.subjects.get(subject.id).role_id == role.id


def test_the_subject_of_the_logged_in_user(client, superset_7):
    me = client.get(client.join_urls(client.base_url, "me/")).json()["result"]

    subject = client.subjects.for_user(me["id"])

    assert (subject.type, subject.user_id) == (SubjectType.USER, me["id"])


def test_a_principal_without_a_subject_is_not_found(client, superset_7):
    with pytest.raises(NotFound):
        client.subjects.for_role(10**9)

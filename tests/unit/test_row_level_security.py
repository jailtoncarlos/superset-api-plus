"""Row level security rules (Superset 7.0): tables and subjects given as saved objects or ids are sent as ids, read ones
as read; users and roles become their subjects; a Regular rule needs a subject.

That the server accepts the requests and applies the clause is tested in tests/integration/test_row_level_security.py;
the payloads are checked against the specification in test_openapi_conformance.py.
"""
import warnings
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from supersetapiplus.core.types import RowLevelSecurityFilterType
from supersetapiplus.exceptions import ValidationError as SupersetApiPlusValidationError
from supersetapiplus.resources.datasets import Dataset
from supersetapiplus.resources.repository import _resolve_subject_aliases
from supersetapiplus.resources.row_level_security import RowLevelSecurityRule
from supersetapiplus.resources.security import Role, Subject

READ = {"id": 9, "name": "Rule", "filter_type": "Regular", "clause": "category <> 'x'", "group_key": "g",
        "description": "d", "tables": [{"id": 4, "schema": "public", "table_name": "t"}],
        "subjects": [{"id": 3, "label": "Public", "type": 2}]}


class FakeSubjects:
    """client.subjects stand-in: the subject of user n is 100 + n, of role n is 200 + n."""

    def for_user(self, user_id):
        return SimpleNamespace(id=100 + user_id)

    def for_role(self, role_id):
        return SimpleNamespace(id=200 + role_id)


def test_saved_tables_and_subjects_are_sent_as_ids():
    rule = RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.BASE, clause="1 = 1",
                                tables=[Dataset(id=4, table_name="t"), 5], subjects=[Subject(id=3, label="Public")])

    assert rule.to_json(list(rule.POST_FIELDS)) == {"name": "Rule", "filter_type": "Base", "clause": "1 = 1",
                                                     "tables": [4, 5], "subjects": [3], "group_key": None,
                                                     "description": None}


def test_a_rule_read_from_superset_keeps_tables_and_subjects_and_writes_their_ids():
    rule = RowLevelSecurityRule.from_json(READ)

    assert rule.filter_type == RowLevelSecurityFilterType.REGULAR
    assert rule.tables == READ["tables"] and rule.subjects == READ["subjects"]
    payload = rule.to_json(list(rule.PUT_FIELDS))
    assert (payload["tables"], payload["subjects"]) == ([4], [3])


def test_users_and_roles_become_their_subjects_and_roles_is_deprecated():
    rule = RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.REGULAR, clause="1 = 1",
                                tables=[4], subjects=[7], users=[1], roles=[Role(id=2, name="Gamma")])

    with pytest.warns(DeprecationWarning, match="RowLevelSecurityRule.roles is deprecated") as record:
        _resolve_subject_aliases(rule, FakeSubjects())

    assert len(record) == 1  # users is not deprecated
    assert (rule.subjects, rule.users, rule.roles) == ([7, 202, 101], [], [])
    assert rule.to_json(list(rule.POST_FIELDS))["subjects"] == [7, 202, 101]


def test_a_regular_rule_needs_a_subject_a_base_rule_does_not():
    regular = RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.REGULAR, clause="1 = 1",
                                   tables=[4])
    with pytest.raises(SupersetApiPlusValidationError, match="a Regular rule needs at least one subject"):
        regular.to_json(list(regular.POST_FIELDS))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        regular.users = [1]  # a user still to resolve counts
        regular.to_json(list(regular.POST_FIELDS))
    base = RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.BASE, clause="1 = 1", tables=[4])
    assert base.to_json(list(base.POST_FIELDS))["subjects"] == []


def test_an_unsaved_object_cannot_be_referenced():
    with pytest.raises(ValueError, match="without id"):
        RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.REGULAR, clause="1 = 1",
                             tables=[Dataset(table_name="t")])


def test_a_rule_built_in_code_takes_only_the_official_filter_types():
    with pytest.raises(ValidationError):
        RowLevelSecurityRule(name="Rule", filter_type="Other", clause="1 = 1", tables=[4])

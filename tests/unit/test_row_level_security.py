"""Row level security rules: tables and roles given as saved objects or ids are sent as ids, read ones as read.

That the server accepts the requests and applies the clause is tested in tests/integration/test_row_level_security.py;
the payloads are checked against the specification in test_openapi_conformance.py.
"""
import pytest
from pydantic import ValidationError

from supersetapiplus.core.types import RowLevelSecurityFilterType
from supersetapiplus.resources.datasets import Dataset
from supersetapiplus.resources.row_level_security import RowLevelSecurityRule
from supersetapiplus.resources.security import Role

READ = {"id": 9, "name": "Rule", "filter_type": "Regular", "clause": "category <> 'x'", "group_key": "g",
        "description": "d", "tables": [{"id": 4, "schema": "public", "table_name": "t"}],
        "roles": [{"id": 3, "name": "Public"}]}


def test_saved_tables_and_roles_are_sent_as_ids():
    rule = RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.BASE, clause="1 = 1",
                                tables=[Dataset(id=4, table_name="t"), 5], roles=[Role(id=3, name="Public")])

    assert rule.to_json(list(rule.POST_FIELDS)) == {"name": "Rule", "filter_type": "Base", "clause": "1 = 1", "tables": [4, 5], "roles": [3],
                    "group_key": None, "description": None}


def test_a_rule_read_from_superset_keeps_tables_and_roles_and_writes_their_ids():
    rule = RowLevelSecurityRule.from_json(READ)

    assert rule.filter_type == RowLevelSecurityFilterType.REGULAR
    assert rule.tables == READ["tables"] and rule.roles == READ["roles"]
    payload = rule.to_json(list(rule.PUT_FIELDS))
    assert (payload["tables"], payload["roles"]) == ([4], [3])


def test_an_unsaved_object_cannot_be_referenced():
    with pytest.raises(ValueError, match="without id"):
        RowLevelSecurityRule(name="Rule", filter_type=RowLevelSecurityFilterType.REGULAR, clause="1 = 1",
                             tables=[Dataset(table_name="t")])


def test_a_rule_built_in_code_takes_only_the_official_filter_types():
    with pytest.raises(ValidationError):
        RowLevelSecurityRule(name="Rule", filter_type="Other", clause="1 = 1", tables=[4])

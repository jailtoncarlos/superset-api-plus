"""Renamed public names keep working as aliases and emit DeprecationWarning (AGENTS.md: public API stability)."""
import importlib
import sys

import pytest

from supersetapiplus.charts import queries, types
from supersetapiplus.dashboards import dashboards, metadata
from supersetapiplus.dashboards.layout.legacy import metadata_position as metadataposition

RENAMED_ATTRIBUTES = [
    (types, "StackStylyType", "StackStyleType"),
    (types, "TitlepositionType", "TitlePositionType"),
    (types, "CurrentPositionType", "CurrencyPositionType"),
    (queries, "QuerieExtra", "QueryExtra"),
    (metadata, "GlobalChartconfiguration", "GlobalChartConfiguration"),
    (metadata, "GlobalChartconfigurationScope", "GlobalChartConfigurationScope"),
    (metadataposition, "Metadataposition", "MetadataPosition"),
    (dashboards, "defult_metadata", "default_metadata"),
    (dashboards, "defult_metadata_position", "default_metadata_position"),
]
RENAMED_MEMBERS = [
    (types.ChartType, "PIVOT_TALBE_V2", "PIVOT_TABLE_V2"),
    (types.LabelType, "CATEGORI_VALUE_AND_PERCENTAG", "CATEGORY_VALUE_AND_PERCENTAGE"),
    (types.FilterOperatorType, "NOT_EQUAL", "NOT_EQUALS"),
]


@pytest.mark.parametrize("module,old,new", RENAMED_ATTRIBUTES, ids=[old for _, old, _ in RENAMED_ATTRIBUTES])
def test_renamed_attribute_is_an_alias_that_warns(module, old, new):
    with pytest.warns(DeprecationWarning, match=new):
        alias = getattr(module, old)
    assert alias is getattr(module, new)


@pytest.mark.parametrize("enum_cls,old,new", RENAMED_MEMBERS, ids=[old for _, old, _ in RENAMED_MEMBERS])
def test_renamed_enum_member_is_an_alias_that_warns(enum_cls, old, new):
    with pytest.warns(DeprecationWarning, match=new):
        alias = getattr(enum_cls, old)
    assert alias is enum_cls[new]
    assert old not in enum_cls.__members__, "the old name is not listed as a member"


@pytest.mark.parametrize("old,new", [("nodeposisition", "layout.legacy.nodes"), ("treenodeposisition", "layout.legacy.tree")])
def test_misspelled_modules_still_import_with_a_warning(old, new):
    sys.modules.pop(f"supersetapiplus.dashboards.{old}", None)
    with pytest.warns(DeprecationWarning, match=new):
        legacy = importlib.import_module(f"supersetapiplus.dashboards.{old}")
    assert legacy.NodePosition is importlib.import_module(f"supersetapiplus.dashboards.{new}").NodePosition


def test_unknown_attribute_still_raises_attribute_error():
    with pytest.raises(AttributeError):
        types.DoesNotExist  # noqa: B018
    with pytest.raises(AttributeError):
        types.ChartType.DOES_NOT_EXIST  # noqa: B018


MOVED_MODULES = [
    ("supersetapiplus.utils.request_handler", "supersetapiplus.transport.http", "RequestHandler"),
    ("supersetapiplus.utils.sensitive", "supersetapiplus.core.masking", "mask_data"),
    ("supersetapiplus.utils.dict_utils", "supersetapiplus.core.dicts", "detailed_dict_diff"),
    ("supersetapiplus.security.csrf", "supersetapiplus.auth.csrf", "CSRFSupportMixin"),
    ("supersetapiplus.security.session_auth", "supersetapiplus.auth.session", "SessionAuthMixin"),
    ("supersetapiplus.base.base", "supersetapiplus.core.model", "SerializableModel"),
    ("supersetapiplus.base.fields", "supersetapiplus.core.fields", "object_field"),
    ("supersetapiplus.base.sentinels", "supersetapiplus.core.sentinels", "MissingField"),
    ("supersetapiplus.typing", "supersetapiplus.core.typing", "SerializableOptional"),
    ("supersetapiplus.base.types", "supersetapiplus.core.types", "DatasourceType"),
    ("supersetapiplus.base.datasource", "supersetapiplus.core.datasource", "DataSource"),
    ("supersetapiplus.dashboards.itemposition", "supersetapiplus.dashboards.layout.legacy.items", "ItemPosition"),
    ("supersetapiplus.dashboards.nodeposition", "supersetapiplus.dashboards.layout.legacy.nodes", "NodePosition"),
    ("supersetapiplus.dashboards.treenodeposition", "supersetapiplus.dashboards.layout.legacy.tree", "TreeNodePosition"),
    ("supersetapiplus.dashboards.metadataposition", "supersetapiplus.dashboards.layout.legacy.metadata_position",
     "MetadataPosition"),
]


@pytest.mark.parametrize("old,new,name", MOVED_MODULES, ids=[old for old, _, _ in MOVED_MODULES])
def test_moved_modules_still_import_with_a_warning(old, new, name):
    sys.modules.pop(old, None)
    with pytest.warns(DeprecationWarning, match=new):
        legacy = importlib.import_module(old)
    assert getattr(legacy, name) is getattr(importlib.import_module(new), name)

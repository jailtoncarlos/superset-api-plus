"""Native filter defaults (defaultDataMask as SelectFilterPlugin builds it) and target column checks."""
import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.native_filters import FilterType, select_default_data_mask, value_label
from supersetapiplus.datasets import Dataset

# Columns as GET /api/v1/dataset/{pk} returns them (type_generic: 0 numeric, 1 string, 2 temporal).
COLUMNS = [
    {"column_name": "campus", "type": "STRING", "type_generic": 1},
    {"column_name": "total", "type": "INTEGER", "type_generic": 0},
    {"column_name": "day", "type": "DATE", "type_generic": 2},
]


def read_dataset() -> Dataset:
    return Dataset(id=7, table_name="sales", columns=[dict(column) for column in COLUMNS])


def new_filter(**options):
    dashboard = Dashboard(dashboard_title="P")
    dashboard.reset_layout()
    return dashboard.json_metadata.add_native_filter("Campus", read_dataset(), "campus", **options).config


def test_default_value_becomes_the_data_mask_the_editor_saves():
    config = new_filter(default_value=["North", "South"])

    assert config["defaultDataMask"] == {
        "extraFormData": {"filters": [{"col": "campus", "op": "IN", "val": ["North", "South"]}]},
        "filterState": {"value": ["North", "South"], "label": "North, South", "excludeFilterValues": True},
        "ownState": {},
    }


def test_single_default_value_and_value_labels():
    config = new_filter(default_value="North", multiSelect=False)

    assert config["defaultDataMask"]["filterState"]["value"] == ["North"]
    assert [value_label(v) for v in (None, True, False, 2.0, 2.5, 3)] == ["<NULL>", "TRUE", "FALSE", "2", "2.5", "3"]


def test_inverse_selection_excludes_the_default_values():
    mask = select_default_data_mask("campus", ["North"], {"inverseSelection": True})

    assert mask["extraFormData"] == {"filters": [{"col": "campus", "op": "NOT IN", "val": ["North"]}]}
    assert mask["filterState"]["label"] == "North (excluded)"


def test_empty_default_of_a_required_filter_selects_nothing():
    mask = select_default_data_mask("campus", [], {"enableEmptyFilter": True})

    assert mask["extraFormData"] == {
        "adhoc_filters": [{"expressionType": "SQL", "clause": "WHERE", "sqlExpression": "1 = 0"}]}
    assert select_default_data_mask("campus", [], {})["extraFormData"] == {}


@pytest.mark.parametrize("options, message", [
    ({"default_value": ["A", "B"], "multiSelect": False}, "single-select"),
    ({"default_value": ["A"], "defaultToFirstItem": True}, "exclusive"),
    ({"default_value": ["A"], "defaultDataMask": {"filterState": {}}}, "not both"),
    ({"default_value": [1], "filter_type": FilterType.RANGE}, "select filters"),
])
def test_default_value_conflicts_are_rejected(options, message):
    column = "total" if options.get("filter_type") == FilterType.RANGE else "campus"
    dashboard = Dashboard(dashboard_title="P")
    with pytest.raises(ValueError, match=message):
        dashboard.json_metadata.add_native_filter("F", read_dataset(), column, **options)


def test_filter_without_default_keeps_the_empty_data_mask():
    assert new_filter()["defaultDataMask"] == {"extraFormData": {}, "filterState": {}, "ownState": {}}


def test_target_column_is_checked_against_the_dataset_read_from_superset():
    metadata = Dashboard(dashboard_title="P").json_metadata

    with pytest.raises(ValueError, match="'region' is not in the dataset"):
        metadata.add_native_filter("Region", read_dataset(), "region")
    with pytest.raises(ValueError, match="range filter needs a numeric column; 'day' is DATE"):
        metadata.add_native_filter("Day", read_dataset(), "day", filter_type=FilterType.RANGE)

    metadata.add_native_filter("Total", read_dataset(), "total", filter_type=FilterType.RANGE)
    metadata.add_native_filter("Region", 7, "region")  # dataset id: nothing to check offline

"""Dashboard layout builder (position_json) and native filters (json_metadata.native_filter_configuration)."""
import json
from collections import Counter

import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.dashboards.native_filters import FilterType
from supersetapiplus.datasets import Dataset
from supersetapiplus.exceptions import NodePositionValidationError


def layout_of(dashboard: Dashboard) -> dict:
    return json.loads(dashboard.to_json()["position_json"])


def filters_of(dashboard: Dashboard) -> list:
    return json.loads(dashboard.to_json()["json_metadata"])["native_filter_configuration"]


def build_panel() -> Dashboard:
    dashboard = Dashboard(dashboard_title="Panel")
    pos = dashboard.reset_layout()
    tabs = pos.add_tabs()
    general = pos.add_tab("General", parent=tabs)
    row = pos.add_row(parent=general)
    pos.add_markdown("## Section", parent=row, height=None, width=12)
    row = pos.add_row(parent=general)
    pos.add_chart(ChartRef(1, "A", "uuid-a"), title="A on the panel", parent=row, width=6, id="CHART-a")
    pos.add_chart(ChartRef(2, "B"), parent=row, width=6)
    pos.add_divider(parent=general)
    details = pos.add_tab("Details", parent=tabs)
    sub_tabs = pos.add_tabs(parent=details)
    sub = pos.add_tab("Sub", parent=sub_tabs)
    pos.add_chart(ChartRef(3, "C"), parent=pos.add_row(parent=sub), width=12)
    return dashboard


def test_new_dashboard_layout_has_root_grid_and_title_header():
    layout = layout_of(Dashboard(dashboard_title="Panel"))

    assert layout["DASHBOARD_VERSION_KEY"] == "v2"
    assert layout["ROOT_ID"]["children"] == ["GRID_ID"]
    assert layout["GRID_ID"] == {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]}
    assert layout["HEADER_ID"]["meta"]["text"] == "Panel"


def test_top_level_tabs_go_inside_the_grid():
    layout = layout_of(build_panel())

    top = layout["GRID_ID"]["children"]
    assert [layout[c]["type"] for c in top] == ["TABS"]
    assert layout[top[0]]["parents"] == ["ROOT_ID", "GRID_ID"]


def test_built_layout_is_consistent_and_keeps_insertion_order():
    layout = layout_of(build_panel())
    items = {k: v for k, v in layout.items() if isinstance(v, dict)}

    for item_id, item in items.items():
        for child in item.get("children", []):
            assert items[child]["parents"] == item.get("parents", []) + [item_id]
    assert Counter(i["type"] for i in items.values()) == Counter(
        {"ROOT": 1, "GRID": 1, "HEADER": 1, "TABS": 2, "TAB": 3, "ROW": 3, "MARKDOWN": 1, "CHART": 3, "DIVIDER": 1})
    general = next(i for i in items.values() if i["type"] == "TAB" and i["meta"]["text"] == "General")
    assert [items[c]["type"] for c in general["children"]] == ["ROW", "ROW", "DIVIDER"]


def test_chart_meta_follows_the_editor():
    layout = layout_of(build_panel())

    assert layout["CHART-a"]["meta"] == {"chartId": 1, "sliceName": "A", "sliceNameOverride": "A on the panel",
                                         "uuid": "uuid-a", "width": 6, "height": 50}
    markdown = next(v for v in layout.values() if isinstance(v, dict) and v["type"] == "MARKDOWN")
    assert markdown["meta"] == {"code": "## Section", "width": 12}


def test_chart_ids_follow_tree_order():
    assert build_panel().position_json.chart_ids() == [1, 2, 3]


def test_chart_on_a_tab_gets_a_row_and_rows_are_reused_while_there_is_room():
    pos = DashboardLayout.empty()
    tab = pos.add_tab("T")
    for chart_id in (1, 2, 3, 4):
        pos.add_chart(ChartRef(chart_id, f"G{chart_id}"), parent=tab, width=4)

    rows = [c for c in tab.children if c.type == "ROW"]
    assert [len(r.children) for r in rows] == [3, 1]


def test_row_overflow_and_invalid_parents_are_rejected():
    pos = DashboardLayout.empty()
    row = pos.add_row()
    pos.add_chart(ChartRef(1, "A"), parent=row, width=8)

    with pytest.raises(NodePositionValidationError):
        pos.add_chart(ChartRef(2, "B"), parent=row, width=6)
    with pytest.raises(NodePositionValidationError):
        pos.add_tab("T", parent=row)
    with pytest.raises(NodePositionValidationError):
        pos.add_row(parent="ROW-missing")
    with pytest.raises(NodePositionValidationError):
        pos.add_chart(ChartRef(None, "unsaved"), parent=row, width=1)
    with pytest.raises(NodePositionValidationError):
        pos.add_chart(ChartRef(3, "C"), parent=pos.add_row(), id="CHART-dup")
        pos.add_chart(ChartRef(4, "D"), parent=pos.add_row(), id="CHART-dup")


def test_reset_layout_discards_previous_components():
    dashboard = build_panel()

    dashboard.reset_layout()

    assert dashboard.position_json.chart_ids() == []
    assert set(layout_of(dashboard)) == {"DASHBOARD_VERSION_KEY", "ROOT_ID", "GRID_ID", "HEADER_ID"}


def test_title_header_follows_the_dashboard_title_only_for_layouts_built_by_the_library():
    dashboard = Dashboard(dashboard_title="Old")
    dashboard.dashboard_title = "New"
    assert layout_of(dashboard)["HEADER_ID"]["meta"]["text"] == "New"

    loaded = Dashboard.from_json({"id": 1, "dashboard_title": "New", "position_json": json.dumps(
        {"HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": "Kept"}}})})
    assert layout_of(loaded)["HEADER_ID"]["meta"]["text"] == "Kept"


def test_tree_alias_is_deprecated():
    pos = DashboardLayout.empty()
    with pytest.deprecated_call():
        assert pos.tree.chart_ids() == []


def test_native_filters_follow_the_editor_structure_and_scopes():
    dashboard = build_panel()
    meta = dashboard.json_metadata
    meta.clear_native_filters()
    meta.add_filter_divider("Section", "About the section")
    first = meta.add_native_filter("Year", Dataset(id=7, table_name="t"), "year",
                                   adhoc_filters=[{"clause": "WHERE"}], multiSelect=False)
    meta.add_native_filter("Course", "dataset-uuid", "course", parent=[first], inverseSelection=True)

    divider, year, course = filters_of(dashboard)

    assert divider["type"] == "DIVIDER" and divider["title"] == "Section" and divider["id"].startswith(
        "NATIVE_FILTER_DIVIDER-")
    assert year["type"] == "NATIVE_FILTER" and year["filterType"] == "filter_select"
    assert year["targets"] == [{"datasetId": 7, "column": {"name": "year"}}]
    assert year["controlValues"]["multiSelect"] is False and year["adhoc_filters"] == [{"clause": "WHERE"}]
    assert year["defaultDataMask"] == {"extraFormData": {}, "filterState": {}, "ownState": {}}
    assert course["targets"] == [{"datasetUuid": "dataset-uuid", "column": {"name": "course"}}]
    assert course["cascadeParentIds"] == [first.id] and course["controlValues"]["inverseSelection"] is True
    for item in (divider, year, course):
        assert item["scope"] == {"rootPath": ["ROOT_ID"], "excluded": []}
        assert item["chartsInScope"] == [1, 2, 3]
        assert len(item["tabsInScope"]) == 3


def test_excluded_charts_leave_the_scope_and_their_tabs():
    dashboard = build_panel()
    item = dashboard.json_metadata.add_native_filter("Year", 7, "year")
    item.config["scope"]["excluded"] = [3]

    (saved,) = filters_of(dashboard)

    assert saved["chartsInScope"] == [1, 2]
    general = dashboard.position_json.find_tab("General")
    assert saved["tabsInScope"] == [general.id]


def test_native_filters_loaded_from_superset_are_not_rewritten():
    stored = [{"id": "NATIVE_FILTER-x", "type": "NATIVE_FILTER", "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
               "chartsInScope": [99], "tabsInScope": [], "name": "Kept"}]
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}",
                                     "json_metadata": json.dumps({"native_filter_configuration": stored})})

    assert filters_of(dashboard) == stored


def test_dataset_without_id_is_rejected():
    with pytest.raises(TypeError):
        Dashboard().json_metadata.add_native_filter("Year", Dataset(table_name="t"), "year")


def test_filter_without_dataset_has_an_empty_target():
    dashboard = build_panel()
    dashboard.json_metadata.add_native_filter("Period", filter_type=FilterType.TIME)

    (saved,) = filters_of(dashboard)

    assert saved["targets"] == [{}] and saved["filterType"] == "filter_time" and saved["controlValues"] == {}
    with pytest.raises(ValueError):
        dashboard.json_metadata.add_native_filter("Year", column="year")


def test_filter_restricted_to_some_charts_excludes_the_others_of_the_layout():
    dashboard = build_panel()
    meta = dashboard.json_metadata
    only = meta.add_native_filter("Year", 7, "year", charts=[ChartRef(1, "A"), 3])
    meta.add_native_filter("Course", 7, "course", excluded_charts=[2])

    year, course = filters_of(dashboard)

    assert year["id"] == only.id
    assert year["scope"] == {"rootPath": ["ROOT_ID"], "excluded": [2]} and year["chartsInScope"] == [1, 3]
    assert course["scope"] == {"rootPath": ["ROOT_ID"], "excluded": [2]} and course["chartsInScope"] == [1, 3]
    with pytest.raises(ValueError):
        meta.add_native_filter("Both", 7, "x", charts=[1], excluded_charts=[2])


@pytest.mark.parametrize("width,height", [(0, 50), (-1, 50), (13, 50), (4, 0), (4, 4), (4, 101)])
def test_component_sizes_outside_the_editor_grid_are_rejected(width, height):
    pos = Dashboard(dashboard_title="P").reset_layout()

    with pytest.raises(NodePositionValidationError):
        pos.add_chart(ChartRef(1, "A"), width=width, height=height)
    with pytest.raises(NodePositionValidationError):
        pos.add_markdown("text", width=width, height=height)
    assert pos.chart_ids() == []


def test_component_sizes_at_the_grid_limits_are_accepted():
    pos = Dashboard(dashboard_title="P").reset_layout()

    pos.add_chart(ChartRef(1, "A"), width=1, height=5)
    pos.add_markdown("text", width=11, height=100)
    pos.add_markdown("no height", width=12, height=None)

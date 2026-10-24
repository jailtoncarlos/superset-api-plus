"""Dashboard: json_metadata/position_json round trip and consistency of the layout built in code."""
import json

from supersetapiplus.charts.table import TableChart
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout.legacy.metadata_position import MetadataPosition

POSITION = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["TABS-a"], "parents": []},
    "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": [], "parents": ["ROOT_ID"]},
    "TABS-a": {"id": "TABS-a", "type": "TABS", "children": ["TAB-1", "TAB-2"], "parents": ["ROOT_ID"], "meta": {}},
    "TAB-1": {"id": "TAB-1", "type": "TAB", "children": ["ROW-1"], "parents": ["ROOT_ID", "TABS-a"],
              "meta": {"text": "General", "defaultText": "Tab title", "placeholder": "Tab title"}},
    "TAB-2": {"id": "TAB-2", "type": "TAB", "children": ["MARKDOWN-1", "DIVIDER-1"], "parents": ["ROOT_ID", "TABS-a"],
              "meta": {"text": "About", "defaultText": "Tab title", "placeholder": "Tab title"}},
    "ROW-1": {"id": "ROW-1", "type": "ROW", "children": ["CHART-1", "CHART-2"],
              "parents": ["ROOT_ID", "TABS-a", "TAB-1"], "meta": {"background": "BACKGROUND_TRANSPARENT"}},
    "CHART-1": {"id": "CHART-1", "type": "CHART", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-1", "ROW-1"],
                "meta": {"chartId": 11, "height": 50, "sliceName": "A", "uuid": "u-1", "width": 6}},
    "CHART-2": {"id": "CHART-2", "type": "CHART", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-1", "ROW-1"],
                "meta": {"chartId": 12, "height": 50, "sliceName": "B", "sliceNameOverride": "B2", "uuid": "u-2",
                         "width": 6}},
    "MARKDOWN-1": {"id": "MARKDOWN-1", "type": "MARKDOWN", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-2"],
                   "meta": {"code": "# Text", "height": 50, "width": 4}},
    "DIVIDER-1": {"id": "DIVIDER-1", "type": "DIVIDER", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-2"]},
}

METADATA = {
    "color_scheme": "supersetColors", "refresh_frequency": 0, "label_colors": {"A": "#ffffff"},
    "shared_label_colors": [], "color_scheme_domain": [], "expanded_slices": {}, "timed_refresh_immune_slices": [],
    "cross_filters_enabled": True, "default_filters": "{}", "chart_configuration": {},
    "global_chart_configuration": {"scope": {"rootPath": ["ROOT_ID"], "excluded": []}, "chartsInScope": [11, 12]},
    "native_filter_configuration": [], "map_label_colors": {},
}


def exported() -> dict:
    return {"id": 5, "dashboard_title": "Panel", "published": True,
            "position_json": json.dumps(POSITION), "json_metadata": json.dumps(METADATA)}


def field(dashboard: Dashboard, name: str) -> dict:
    value = dashboard.to_json()[name]
    return json.loads(value) if isinstance(value, str) else value


def test_json_metadata_round_trips_without_loss():
    assert field(Dashboard.from_json(exported()), "json_metadata") == METADATA


def test_position_json_round_trips_without_loss():
    assert field(Dashboard.from_json(exported()), "position_json") == POSITION


def test_layout_built_in_code_is_consistent():
    pos = MetadataPosition()
    tab = pos.add_tab("Indicators")
    for chart_id in (1, 2, 3):
        pos.add_chart(TableChart(slice_name=f"G{chart_id}", id=chart_id), f"G{chart_id}", parent=tab, width=6)
    pos.add_markdown("# Notes", parent=tab, width=12)

    layout = pos.to_dict()
    items = {k: v for k, v in layout.items() if isinstance(v, dict)}

    for item_id, item in items.items():
        for child in item["children"]:
            assert child in items, f"{item_id} points to missing child {child}"
            assert items[child]["parents"] == item["parents"] + [item_id]
    charts = [i for i in items.values() if i["type"] == "CHART"]
    assert sorted(g["meta"]["chartId"] for g in charts) == [1, 2, 3]
    rows = [i for i in items.values() if i["type"] == "ROW"]
    assert all(sum(items[c]["meta"]["width"] for c in row["children"]) <= 12 for row in rows)


def test_dashboard_colors_are_read_and_updated_in_json_metadata():
    dashboard = Dashboard.from_json(exported())

    dashboard.update_colors({"B": "#000000"})

    assert dashboard.colors == {"A": "#ffffff", "B": "#000000"}
    assert field(dashboard, "json_metadata")["label_colors"] == {"A": "#ffffff", "B": "#000000"}

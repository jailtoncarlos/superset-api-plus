"""Structural rules of dashboard layouts (isValidChild.ts depths, cycles, parents), on synthetic layouts."""
import copy
import json
import warnings
from pathlib import Path

import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.dashboards.layout.validation import layout_problems
from supersetapiplus.exceptions import LayoutWarning, NodePositionValidationError

# Layouts of the example dashboards of Superset (bin/scripts/extract_example_layouts.py).
EXAMPLES = json.loads((Path(__file__).parents[1] / "fixtures" / "example_layouts_6.1.0.json").read_text())["layouts"]


def component(component_id: str, component_type: str, children=(), parents=None, **meta) -> dict:
    data = {"id": component_id, "type": component_type, "children": list(children), "meta": meta}
    if parents is not None:
        data["parents"] = parents
    return data


def tabbed_layout() -> dict:
    """ROOT → GRID → TABS → TAB → ROW → CHART, with complete parents, as the editor saves it."""
    return {
        "ROOT_ID": component("ROOT_ID", "ROOT", ["GRID_ID"]),
        "GRID_ID": component("GRID_ID", "GRID", ["TABS-1"], ["ROOT_ID"]),
        "TABS-1": component("TABS-1", "TABS", ["TAB-1"], ["ROOT_ID", "GRID_ID"]),
        "TAB-1": component("TAB-1", "TAB", ["ROW-1"], ["ROOT_ID", "GRID_ID", "TABS-1"], text="T"),
        "ROW-1": component("ROW-1", "ROW", ["CHART-1"], ["ROOT_ID", "GRID_ID", "TABS-1", "TAB-1"]),
        "CHART-1": component("CHART-1", "CHART", [], ["ROOT_ID", "GRID_ID", "TABS-1", "TAB-1", "ROW-1"],
                             chartId=1, width=4, height=50),
        "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": "Title"}},
    }


def test_editor_layouts_and_the_empty_map_are_valid():
    assert layout_problems(tabbed_layout()) == []
    assert layout_problems({}) == []
    assert layout_problems(DashboardLayout.empty("T").components) == []


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_example_dashboards_of_superset_are_valid_and_sent_without_warning(name):
    position = EXAMPLES[name]["position"]
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": json.dumps(position)})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sent = json.loads(dashboard.to_json()["position_json"])

    assert dashboard.position.problems() == []
    assert sent == position


def test_missing_parents_are_rebuilt_by_the_frontend_and_accepted():
    layout = tabbed_layout()
    for data in layout.values():
        data.pop("parents", None)

    assert layout_problems(layout, check_parents=True) == []


def test_stale_parents_are_reported_only_on_request():
    layout = tabbed_layout()
    layout["CHART-1"]["parents"] = ["ROOT_ID", "GRID_ID"]

    assert layout_problems(layout) == []
    assert layout_problems(layout, check_parents=True) == [
        "CHART-1: parents ['ROOT_ID', 'GRID_ID'] differ from the path "
        "['ROOT_ID', 'GRID_ID', 'TABS-1', 'TAB-1', 'ROW-1']."]


def test_parents_of_a_layout_built_by_the_library_are_checked():
    pos = DashboardLayout.empty("T")
    row = pos.add_row()
    chart = pos.add_chart(ChartRef(1, "A"), parent=row)
    assert pos.problems() == []

    chart.data["parents"] = ["ROOT_ID"]
    assert pos.problems() == [f"{chart.id}: parents ['ROOT_ID'] differ from the path ['ROOT_ID', 'GRID_ID', '{row.id}']."]


@pytest.mark.parametrize("parent, child, accepted", [
    ("ROW", "ROW", False), ("ROW", "TABS", False), ("TABS", "ROW", False), ("CHART", "ROW", False),
    ("GRID", "CHART", True), ("COLUMN", "TABS", True), ("TAB", "COLUMN", True), ("ROOT", "ROW", False),
])
def test_child_types_follow_is_valid_child(parent, child, accepted):
    layout = {
        "ROOT_ID": component("ROOT_ID", "ROOT", ["P"]),
        "P": component("P", parent, ["C"]),
        "C": component("C", child, ["T"] if child == "TABS" else []),
        "T": component("T", "TAB"),
    }
    if parent == "ROOT":
        layout["ROOT_ID"]["children"] = ["C"]
        del layout["P"]
    if child != "TABS":
        del layout["T"]

    pair = "ROOT_ID" if parent == "ROOT" else "P"
    problems = [p for p in layout_problems(layout)
                if f"{pair} (" in p and ("child (C)" in p or "cannot have children" in p)]

    assert (problems == []) is accepted


def test_tabs_do_not_add_depth_but_rows_and_columns_do():
    # ROOT(0) → GRID(1) → ROW(2) → COLUMN(3) → ROW(4) → COLUMN: COLUMN takes a ROW only up to depth 3.
    layout = {
        "ROOT_ID": component("ROOT_ID", "ROOT", ["GRID_ID"]),
        "GRID_ID": component("GRID_ID", "GRID", ["ROW-1"]),
        "ROW-1": component("ROW-1", "ROW", ["COLUMN-1"]),
        "COLUMN-1": component("COLUMN-1", "COLUMN", ["ROW-2"]),
        "ROW-2": component("ROW-2", "ROW", ["COLUMN-2"]),
        "COLUMN-2": component("COLUMN-2", "COLUMN", ["ROW-3"]),
        "ROW-3": component("ROW-3", "ROW", []),
    }

    assert layout_problems(layout) == ["ROW-3 (ROW) is nested too deeply under COLUMN-2."]

    # The same nesting under tabs: TABS and TAB keep the depth of the grid, so ROW-2 is still accepted.
    nested_tabs = copy.deepcopy(tabbed_layout())
    nested_tabs["TAB-1"]["children"] = ["COLUMN-1"]
    nested_tabs["COLUMN-1"] = component("COLUMN-1", "COLUMN", ["ROW-2"])
    nested_tabs["ROW-2"] = component("ROW-2", "ROW", [])
    del nested_tabs["ROW-1"], nested_tabs["CHART-1"]

    assert layout_problems(nested_tabs) == []


def test_cycles_are_found_without_recursion():
    layout = {
        "ROOT_ID": component("ROOT_ID", "ROOT", ["GRID_ID"]),
        "GRID_ID": component("GRID_ID", "GRID", ["COLUMN-1"]),
        "COLUMN-1": component("COLUMN-1", "COLUMN", ["ROW-1"]),
        "ROW-1": component("ROW-1", "ROW", ["COLUMN-1"]),
    }

    assert layout_problems(layout)[-1].startswith("The layout has a cycle at ")


def test_unknown_child_second_parent_empty_tabs_and_unreachable_components():
    layout = tabbed_layout()
    layout["GRID_ID"]["children"] = ["TABS-1", "MISSING"]
    layout["ROW-2"] = component("ROW-2", "ROW", ["CHART-1"])
    layout["TABS-2"] = component("TABS-2", "TABS", [])

    problems = layout_problems(layout)

    assert "Tabs TABS-2 must contain at least one tab." in problems
    layout["TABS-2"]["children"] = ["TAB-1"]
    problems = layout_problems(layout)
    assert "GRID_ID has unknown child MISSING." in problems
    assert any(p.startswith("CHART-1 has more than one parent") for p in problems)
    assert any(p.startswith("TAB-1 has more than one parent") for p in problems)
    assert "ROW-2 is not reachable from ROOT_ID." in problems


def test_empty_grid_beside_top_level_tabs_is_accepted():
    layout = tabbed_layout()
    layout["ROOT_ID"]["children"] = ["TABS-1"]
    layout["GRID_ID"]["children"] = []
    for data in layout.values():
        data.pop("parents", None)

    assert layout_problems(layout) == []


def test_layout_built_by_the_library_is_validated_before_sending():
    dashboard = Dashboard(dashboard_title="P")
    pos = dashboard.reset_layout()
    pos.add_tabs()  # a TABS without tabs: the dashboard cannot render it

    with pytest.raises(NodePositionValidationError, match="must contain at least one tab"):
        dashboard.to_json()

    pos.add_tab("T")
    pos.add_chart(ChartRef(1, "A"), parent=pos.find_tab("T"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dashboard.to_json()


def test_layout_read_from_superset_is_sent_as_read_with_a_warning():
    stored = tabbed_layout()
    stored["ROW-1"]["children"].append("ROW-2")  # a ROW cannot hold another ROW
    stored["ROW-2"] = component("ROW-2", "ROW", [], [*stored["ROW-1"]["parents"], "ROW-1"])
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": json.dumps(stored)})

    with pytest.warns(LayoutWarning, match=r"ROW-1 \(ROW\) does not accept a ROW child"):
        sent = json.loads(dashboard.to_json()["position_json"])

    assert sent == stored
    with pytest.raises(NodePositionValidationError, match=r"ROW-1 \(ROW\) does not accept a ROW child"):
        dashboard.position.validate()

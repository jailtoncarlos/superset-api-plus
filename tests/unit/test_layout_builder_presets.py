"""Layout builder conveniences: columns, one-call presets, idempotent placement and chart removal."""
import pytest

from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.exceptions import NodePositionValidationError

CHARTS = [ChartRef(i, f"Chart {i}") for i in range(1, 6)]


def types_under(layout: DashboardLayout, component_id: str) -> list:
    return [layout.components[child]["type"] for child in layout.components[component_id]["children"]]


def test_column_lives_in_a_row_and_bounds_the_width_of_its_content():
    layout = DashboardLayout.empty("T")
    column = layout.add_column(width=6)
    layout.add_chart(CHARTS[0], parent=column, width=6)
    layout.add_markdown("text", parent=column, width=3)

    row_id = layout.components[column.id]["parents"][-1]
    assert layout.components[row_id]["type"] == "ROW" and column.meta == {"width": 6, "background":
                                                                          "BACKGROUND_TRANSPARENT"}
    assert types_under(layout, column.id) == ["CHART", "MARKDOWN"]
    with pytest.raises(NodePositionValidationError, match="does not fit in column"):
        layout.add_chart(CHARTS[1], parent=column, width=7)
    layout.add_chart(CHARTS[2], parent=row_id, width=6)  # the column takes 6 of the 12 columns of its row
    with pytest.raises(NodePositionValidationError, match="not enough space"):
        layout.add_column(parent=row_id, width=1)
    assert layout.problems() == []


def test_grid_preset_places_the_charts_in_rows_of_n():
    layout = DashboardLayout.empty("T")

    placed = layout.add_chart_grid(CHARTS, columns=2)

    rows = layout.components["GRID_ID"]["children"]
    assert [len(layout.components[row]["children"]) for row in rows] == [2, 2, 1]
    assert {component.meta["width"] for component in placed} == {6}
    assert layout.chart_ids() == [1, 2, 3, 4, 5] and layout.problems() == []
    with pytest.raises(NodePositionValidationError, match="columns must be 1 to 12"):
        layout.add_chart_grid(CHARTS, columns=13)


def test_tabs_preset_gives_one_tab_per_title_with_its_grid():
    layout = DashboardLayout.empty("T")

    tabs = layout.add_chart_tabs({"Overview": CHARTS[:3], "Details": CHARTS[3:]}, columns=3)

    assert [tab.meta["text"] for tab in tabs.values()] == ["Overview", "Details"]
    assert [len(layout.components[row]["children"]) for row in layout.components[tabs["Overview"].id]["children"]] \
        == [3]
    assert layout.chart_ids() == [1, 2, 3, 4, 5] and layout.problems() == []


def test_skip_existing_does_not_place_a_chart_twice():
    layout = DashboardLayout.empty("T")
    first = layout.add_chart(CHARTS[0])

    again = layout.add_chart(CHARTS[0], skip_existing=True)
    duplicate = layout.add_chart(CHARTS[0])

    assert again == first and duplicate != first and layout.chart_ids() == [1, 1]


def test_remove_chart_prunes_empty_rows_and_columns_and_keeps_the_rest():
    layout = DashboardLayout.empty("T")
    tab = layout.add_chart_tabs({"Only": CHARTS[:2]}, columns=2)["Only"]
    column = layout.add_column(parent=layout.add_row(parent=tab), width=6)
    layout.add_chart(CHARTS[2], parent=column, width=6)
    before = {cid: list(data.get("parents", [])) for cid, data in layout.components.items()}

    assert layout.remove_chart(CHARTS[2]) == 1  # its column and row are now empty: both go
    assert layout.remove_chart(1) == 1
    assert layout.remove_chart(99) == 0

    assert layout.chart_ids() == [2]
    assert types_under(layout, tab.id) == ["ROW"] and column.id not in layout.components
    assert all(layout.components[cid].get("parents", []) == parents
               for cid, parents in before.items() if cid in layout.components)
    assert layout.remove_chart(2) == 1
    assert types_under(layout, tab.id) == [] and layout.problems() == []  # an empty tab stays

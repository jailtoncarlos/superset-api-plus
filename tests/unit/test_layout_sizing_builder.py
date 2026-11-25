"""Content-based heights in the layout builder (add_chart(content=..., height="auto"), add_markdown) and the sizing
check when the layout is sent (position_json.sizing): pure logic, no HTTP."""
import importlib
import warnings

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.dashboards.layout.sizing import (
    BarsContent,
    ChartShape,
    Layout,
    SizingMode,
    TableContent,
    calibrated_profile,
    estimate_horizontal_bars,
    estimate_markdown,
    estimate_pivot_table,
    estimate_table,
)
from supersetapiplus.exceptions import NodePositionValidationError, SizingError, SizingWarning

PROFILE = calibrated_profile()
LABELS = [f"Indicator {i} with a label long enough to wrap in the label column of the table" for i in range(8)]


def chart(viz_type: str, chart_id: int, **params) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    built = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=f"{viz_type} {chart_id}", datasource=DataSource(id=1, type="table"))
    for key, value in params.items():
        setattr(built.params, key, value)
    built.id = chart_id
    return built


def sent(layout: DashboardLayout) -> dict:
    """What the layout sends (the checks before sending run)."""
    return layout.to_dict(convert_to_json=True)


def test_the_calibrated_profile_of_the_target_version_is_shipped_with_the_package():
    assert PROFILE.superset_version == "6.1.0"
    assert set(PROFILE.viewports) == {1366, 1920}
    with pytest.raises(ValueError, match="no calibrated sizing profile"):
        calibrated_profile("0.0.0")


def test_auto_height_of_a_table_is_the_recommended_height_of_its_content():
    layout = DashboardLayout.empty()
    content = TableContent(rows=8, labels=LABELS, title="Indicators")
    component = layout.add_chart(chart("table", 1), "Indicators", width=8, height="auto", content=content)
    assert component.meta["height"] == estimate_table(content, PROFILE, Layout(columns=8)).recommended_units


def test_auto_height_of_pivot_tables_and_horizontal_bars_uses_their_formulas():
    layout = DashboardLayout.empty()
    table = TableContent(rows=12, title="Pivot")
    bars = BarsContent(bars=6, labels=LABELS[:6], title="Bars")
    pivot = layout.add_chart(chart("pivot_table_v2", 1), height="auto", width=12, content=table)
    horizontal = layout.add_chart(chart("echarts_timeseries_bar", 2, orientation="horizontal"), height="auto",
                                  width=12, content=bars, max_rows=4)
    assert pivot.meta["height"] == estimate_pivot_table(table, PROFILE).recommended_units
    assert horizontal.meta["height"] == estimate_horizontal_bars(bars, PROFILE, max_rows=4).recommended_units


def test_a_chart_ref_is_sized_as_a_table_or_horizontal_bars_by_its_content():
    layout = DashboardLayout.empty()
    content = TableContent(rows=3)
    component = layout.add_chart(ChartRef(1, "Saved table"), height="auto", width=6, content=content)
    assert component.meta["height"] == estimate_table(content, PROFILE, Layout(columns=6)).recommended_units


def test_a_chart_ref_declaring_a_pivot_table_is_sized_as_the_same_chart_with_its_params():
    content = TableContent(rows=12, labels=LABELS[:4], title="Pivot")
    layout = DashboardLayout.empty()
    by_reference = layout.add_chart(ChartRef(1, "Saved pivot", shape=ChartShape.PIVOT_TABLE), height="auto",
                                    width=8, content=content)
    with_params = layout.add_chart(chart("pivot_table_v2", 2), height="auto", width=8, content=content)
    as_table = layout.add_chart(ChartRef(3, "Saved pivot"), height="auto", width=8, content=content)
    assert by_reference.meta["height"] == with_params.meta["height"] == estimate_pivot_table(
        content, PROFILE, Layout(columns=8)).recommended_units
    assert as_table.meta["height"] == estimate_table(content, PROFILE, Layout(columns=8)).recommended_units
    assert as_table.meta["height"] != by_reference.meta["height"]  # without the shape: sized as a table


def test_the_shape_of_a_chart_ref_must_match_the_content():
    with pytest.raises(NodePositionValidationError, match="TableContent describes .*, not a horizontal_bars chart"):
        DashboardLayout.empty().add_chart(ChartRef(1, "Bars", shape=ChartShape.HORIZONTAL_BARS), height="auto",
                                          content=TableContent(rows=3))


def test_the_content_is_kept_by_the_library_and_never_written_to_position_json():
    with_content, without = DashboardLayout.empty("Dash"), DashboardLayout.empty("Dash")
    content = TableContent(rows=8, labels=LABELS, title="Indicators")
    height = with_content.add_chart(chart("table", 1), parent=with_content.add_row(id="ROW-a"), width=12,
                                    height="auto", content=content, id="CHART-a")
    without.add_chart(chart("table", 1), parent=without.add_row(id="ROW-a"), width=12, height=height.meta["height"],
                      id="CHART-a")
    assert sent(with_content) == sent(without)
    assert "Indicator" not in str(sent(with_content))


def test_auto_height_needs_the_content():
    with pytest.raises(NodePositionValidationError, match="needs the content"):
        DashboardLayout.empty().add_chart(chart("table", 1), height="auto")


def test_the_content_must_match_the_chart():
    layout = DashboardLayout.empty()
    with pytest.raises(NodePositionValidationError, match="BarsContent describes horizontal_bars, not a table"):
        layout.add_chart(chart("table", 1), height="auto", content=BarsContent(bars=3))
    with pytest.raises(NodePositionValidationError, match="not a pie chart"):
        layout.add_chart(chart("pie", 2), height="auto", content=TableContent(rows=3))
    # Vertical bars are not sized: only horizontal ones.
    with pytest.raises(NodePositionValidationError, match="not a echarts_timeseries_bar chart"):
        layout.add_chart(chart("echarts_timeseries_bar", 3), height="auto", content=BarsContent(bars=3))
    assert layout.chart_ids() == []


def test_a_height_that_does_not_fit_the_content_warns_when_the_layout_is_sent():
    layout = DashboardLayout.empty()
    layout.add_chart(chart("table", 1), "Indicators", width=12, height=10, content=TableContent(rows=8, labels=LABELS))
    with pytest.warns(SizingWarning, match=r"Indicators: height 10 is below the content's minimum of \d+ units"):
        sent(layout)


def test_the_sizing_check_can_be_turned_off_or_made_strict():
    layout = DashboardLayout.empty()
    layout.add_chart(chart("table", 1), width=12, height=10, content=TableContent(rows=8, labels=LABELS))
    layout.sizing = "off"
    with warnings.catch_warnings():
        warnings.simplefilter("error", SizingWarning)
        sent(layout)
    layout.sizing = SizingMode.STRICT
    with pytest.raises(SizingError, match="below the content's minimum"):
        sent(layout)
    with pytest.raises(ValueError):
        layout.sizing = "sometimes"


def test_strict_mode_only_warns_on_pivot_tables_whose_estimate_is_approximate():
    layout = DashboardLayout.empty()
    layout.sizing = "strict"
    layout.add_chart(chart("pivot_table_v2", 1), width=12, height=5, content=TableContent(rows=30))
    with pytest.warns(SizingWarning, match="approximate"):
        sent(layout)


def test_heights_that_fit_send_without_warnings():
    layout = DashboardLayout.empty()
    layout.sizing = "strict"
    layout.add_chart(chart("table", 1), width=12, height="auto", content=TableContent(rows=8, labels=LABELS))
    layout.add_markdown("## Section\n\nA short paragraph.", width=12, height="auto")
    with warnings.catch_warnings():
        warnings.simplefilter("error", SizingWarning)
        sent(layout)


def test_a_height_changed_after_placing_the_chart_is_checked():
    layout = DashboardLayout.empty()
    component = layout.add_chart(chart("table", 1), width=12, height="auto", content=TableContent(rows=8))
    component.meta["height"] = 100
    with pytest.warns(SizingWarning, match="more empty space than tolerated"):
        sent(layout)


def test_markdown_is_sized_from_its_text_and_checked_when_sent():
    layout = DashboardLayout.empty()
    text = "# Title\n\n" + "\n\n".join(f"Paragraph {i} of the markdown block." for i in range(10))
    auto = layout.add_markdown(text, width=6, height="auto")
    assert auto.meta["height"] == estimate_markdown(text, PROFILE, Layout(columns=6)).recommended_units
    layout.add_markdown(text, width=6, height=5)
    with pytest.warns(SizingWarning, match="markdown MARKDOWN-.+: height 5 is below"):
        sent(layout)


def test_markdown_that_cannot_be_measured_needs_an_explicit_height():
    layout = DashboardLayout.empty()
    with pytest.raises(NodePositionValidationError, match="cannot be sized automatically"):
        layout.add_markdown("![logo](logo.png)", height="auto")
    layout.add_markdown("![logo](logo.png)", height=20)  # given: kept and not checked
    with warnings.catch_warnings():
        warnings.simplefilter("error", SizingWarning)
        sent(layout)


def test_a_layout_read_from_superset_is_not_sized():
    built = DashboardLayout.empty()
    built.add_chart(chart("table", 1), width=12, height=5, content=TableContent(rows=40))
    read = DashboardLayout.from_json(built.to_dict())
    with warnings.catch_warnings():
        warnings.simplefilter("error", SizingWarning)
        sent(read)


def test_another_profile_can_be_given():
    layout = DashboardLayout.empty()
    content = TableContent(rows=8)
    roomy = PROFILE.model_copy(update={"table": PROFILE.table.model_copy(update={"row": PROFILE.table.row * 2})})
    layout.sizing_profile = roomy
    component = layout.add_chart(chart("table", 1), width=12, height="auto", content=content)
    assert component.meta["height"] == estimate_table(content, roomy).recommended_units
    assert component.meta["height"] > estimate_table(content, PROFILE).recommended_units


def test_a_removed_chart_leaves_no_content_behind_for_a_component_with_its_id():
    layout = DashboardLayout.empty()
    layout.sizing = "strict"
    table = chart("table", 1)
    layout.add_chart(table, width=12, height="auto", content=TableContent(rows=30), id="CHART-a")
    layout.remove_chart(table)
    layout.add_chart(chart("table", 2), width=12, height=8, id="CHART-a")  # placed without content: not checked
    with warnings.catch_warnings():
        warnings.simplefilter("error", SizingWarning)
        sent(layout)


def test_markdown_edited_after_placing_it_is_checked_against_its_current_text():
    layout = DashboardLayout.empty()
    layout.sizing = "strict"
    component = layout.add_markdown("A short line.", width=6, height="auto")
    component.meta["code"] = "\n\n".join(f"Paragraph {i} of a much longer text." for i in range(20))
    with pytest.raises(SizingError, match="below the content's minimum"):
        sent(layout)


LONG_TITLE = "A title long enough to wrap in several lines on a chart only three grid columns wide"


def test_the_title_measured_is_the_one_the_chart_shows():
    layout = DashboardLayout.empty()
    content = TableContent(rows=3)  # no title in the content
    placed = layout.add_chart(chart("table", 1), LONG_TITLE, width=3, height="auto", content=content)
    expected = estimate_table(TableContent(rows=3, title=LONG_TITLE), PROFILE, Layout(columns=3)).recommended_units
    assert placed.meta["height"] == expected
    assert expected > estimate_table(content, PROFILE, Layout(columns=3)).recommended_units


def test_a_title_changed_after_placing_the_chart_is_checked():
    layout = DashboardLayout.empty()
    layout.sizing = "strict"
    placed = layout.add_chart(chart("table", 1), "Short", width=3, height="auto", content=TableContent(rows=3))
    placed.meta["sliceNameOverride"] = LONG_TITLE
    with pytest.raises(SizingError, match="below the content's minimum"):
        sent(layout)


# Twelve paragraphs that wrap in one line more on a 4-column block when the vertical filter bar narrows the grid.
TEXT = "\n\n".join(" ".join(["word"] * 9) for _ in range(12))


def dashboard_with_filters(orientation: str | None) -> Dashboard:
    dashboard = Dashboard(dashboard_title="Filters")
    dashboard.json_metadata.add_native_filter("Region", dataset=1, column="region")
    if orientation:
        dashboard.json_metadata.filter_bar_orientation = orientation
    return dashboard


def full_width_minimum(text: str, columns: int) -> int:
    return estimate_markdown(text, PROFILE, Layout(columns=columns, vertical_filter_bar=False)).min_units


def test_a_dashboard_with_the_filter_bar_on_top_is_sized_on_the_full_grid_width():
    dashboard = dashboard_with_filters("HORIZONTAL")
    dashboard.position.sizing = "strict"
    height = full_width_minimum(TEXT, 4)
    assert height < estimate_markdown(TEXT, PROFILE, Layout(columns=4)).min_units  # the bar matters here
    dashboard.position.add_markdown(TEXT, width=4, height=height)
    dashboard.to_dict(convert_to_json=True)  # no SizingError: the grid is not narrowed by a vertical bar
    auto = dashboard.position.add_markdown(TEXT, width=4, height="auto")
    assert auto.meta["height"] == estimate_markdown(TEXT, PROFILE, Layout(columns=4, vertical_filter_bar=False)) \
        .recommended_units


def test_the_vertical_filter_bar_narrows_the_grid_when_the_dashboard_shows_it():
    dashboard = dashboard_with_filters(None)  # vertical, the default
    dashboard.position.sizing = "strict"
    assert dashboard.position.vertical_filter_bar
    dashboard.position.add_markdown(TEXT, width=4, height=full_width_minimum(TEXT, 4))
    with pytest.raises(SizingError):
        dashboard.to_dict(convert_to_json=True)


def test_without_native_filters_there_is_no_filter_bar_and_the_user_can_force_it():
    dashboard = Dashboard(dashboard_title="No filters")
    assert dashboard.position.vertical_filter_bar is False
    dashboard.position.vertical_filter_bar = True
    assert dashboard.position.vertical_filter_bar is True
    assert DashboardLayout.empty().vertical_filter_bar  # a layout on its own assumes the bar


def test_markdown_and_charts_inside_a_column_are_sized_at_the_column_width():
    layout = DashboardLayout.empty()
    column = layout.add_column(parent=layout.add_row(), width=4)
    # Placed 12 wide would fail (a component is at most as wide as its column): the builder keeps it within, and a
    # layout read from Superset may carry a wider meta width; either way the column's width is what is drawn.
    markdown = layout.add_markdown(TEXT, parent=column, width=4, height="auto")
    narrow = estimate_markdown(TEXT, PROFILE, Layout(columns=4)).recommended_units
    assert markdown.meta["height"] == narrow
    markdown.meta["width"] = 12  # as stored by an editor that left a stale width
    assert layout.rendered_width(markdown.id) == 4
    layout.sizing = "strict"
    sent(layout)  # checked at the column width (4), where the height fits


def test_a_chart_nested_below_a_column_is_at_most_as_wide_as_it():
    layout = DashboardLayout.empty()
    column = layout.add_column(parent=layout.add_row(), width=6)
    inner = layout.add_row(parent=column)
    component = layout.add_chart(chart("table", 1), parent=inner, width=6, height="auto", content=TableContent(rows=3))
    component.meta["width"] = 12
    assert layout.rendered_width(component.id) == 6


def test_a_markdown_narrower_than_its_column_is_drawn_and_sized_at_the_column_width():
    layout = DashboardLayout.empty()
    column = layout.add_column(parent=layout.add_row(), width=6)
    markdown = layout.add_markdown(TEXT, parent=column, width=3, height="auto")
    assert layout.rendered_width(markdown.id) == 6
    assert markdown.meta["height"] == estimate_markdown(TEXT, PROFILE, Layout(columns=6)).recommended_units
def test_filters_added_after_the_layout_was_taken_count():
    dashboard = Dashboard(dashboard_title="Built in steps")
    layout = dashboard.reset_layout()  # taken before the filters exist
    assert layout.vertical_filter_bar is False
    dashboard.json_metadata.add_native_filter("Region", dataset=1, column="region")
    assert layout.vertical_filter_bar is True
    auto = layout.add_markdown(TEXT, width=4, height="auto")
    assert auto.meta["height"] == estimate_markdown(TEXT, PROFILE, Layout(columns=4)).recommended_units


def test_every_builder_path_of_a_dashboard_follows_its_filter_bar():
    dashboard = Dashboard(dashboard_title="Direct")  # no filters: no bar
    direct = dashboard.position_json.add_markdown(TEXT, width=4, height="auto")  # no prior access to .position
    full_width = estimate_markdown(TEXT, PROFILE, Layout(columns=4, vertical_filter_bar=False)).recommended_units
    assert direct.meta["height"] == full_width
    dashboard.position_json = DashboardLayout.empty("Replaced")  # an assigned layout follows the dashboard too
    dashboard.json_metadata.add_native_filter("Region", dataset=1, column="region")
    assert dashboard.position_json.vertical_filter_bar is True
    dashboard.position.sizing = "strict"
    dashboard.position.add_markdown(TEXT, width=4, height="auto")
    dashboard.to_dict(convert_to_json=True)  # sized and checked with the same bar: no SizingError


def test_a_cyclic_layout_does_not_hang_the_width_and_is_reported_by_the_validation():
    layout = DashboardLayout.empty()
    row = layout.add_row()
    component = layout.add_chart(chart("table", 1), parent=row, width=6, height="auto", content=TableContent(rows=3))
    other = layout.add_row()
    # Rows inside each other, out of the grid: a cycle without a COLUMN above the chart.
    layout.components["GRID_ID"]["children"] = []
    layout.components[row.id]["children"].append(other.id)
    layout.components[other.id]["children"].append(row.id)
    assert layout.rendered_width(component.id) == 6
    with pytest.raises(NodePositionValidationError):
        sent(layout)

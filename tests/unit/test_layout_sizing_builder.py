"""Content-based heights in the layout builder (add_chart(content=..., height="auto"), add_markdown) and the sizing
check when the layout is sent (position_json.sizing): pure logic, no HTTP."""
import importlib
import warnings

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.dashboards.layout.sizing import (
    BarsContent,
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

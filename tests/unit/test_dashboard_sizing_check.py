"""Content of a saved chart read from the chart data result (services.dashboard_sizing): pure logic, no HTTP. The
check against Superset is in tests/integration (test_dashboards.py and every example dashboard)."""
import importlib

from supersetapiplus.charts.charts import Chart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.layout.sizing import ChartShape, SizingEstimate, calibrated_profile
from supersetapiplus.services.dashboard_sizing import (
    ComponentSizing,
    DashboardSizing,
    SizingReport,
    _bars_content,
    _pivot_content,
    _table_content,
)

ROWS = [{"campus": f"Campus {i}", "region": "North" if i % 2 else "South", "count": i} for i in range(12)]
RESULT = {"rowcount": 12, "colnames": ["campus", "count"], "data": ROWS}


def test_table_rows_and_labels_come_from_the_first_column():
    content = _table_content({"viz_type": "table"}, RESULT, "By campus")
    assert (content.rows, content.labels[:2], content.title) == (12, ["Campus 0", "Campus 1"], "By campus")
    assert not (content.search or content.pagination or content.fixed_label_width)


def test_a_paginated_table_shows_one_page_with_its_controls():
    client_side = _table_content({"page_length": 5, "include_search": True}, RESULT, "")
    server_side = _table_content({"server_pagination": True, "server_page_length": 10}, RESULT, "")
    assert (client_side.rows, client_side.pagination, client_side.search) == (5, True, True)
    assert (server_side.rows, server_side.pagination) == (10, True)


def test_a_label_column_with_a_fixed_width_is_known():
    content = _table_content({"column_config": {"campus": {"columnWidth": 560}}}, RESULT, "")
    assert content.fixed_label_width


def test_pivot_rows_are_the_distinct_values_of_its_row_dimensions_plus_totals():
    params = {"groupbyRows": ["region", {"label": "campus", "sqlExpression": "campus"}], "colTotals": True}
    content = _pivot_content(params, RESULT, "")
    assert content.rows == 13  # 12 (region, campus) pairs and the totals row
    assert _pivot_content({"groupbyRows": ["region"]}, RESULT, "").labels == ["South", "North"]


def test_bars_are_the_distinct_values_of_the_x_axis():
    content = _bars_content({"x_axis": "region", "show_legend": False}, RESULT, "Regions")
    assert (content.bars, content.labels, content.legend) == (2, ["South", "North"], False)


def test_the_report_lists_problems_and_summarizes_each_component():
    fits = ComponentSizing("CHART-a", "Campus", ChartShape.TABLE, 6, 40, SizingEstimate(30, 31, 45))
    cut = ComponentSizing("CHART-b", "Regions", ChartShape.TABLE, 6, 10, SizingEstimate(30, 31, 45),
                          problem="height 10 is below the content's minimum of 30 units")
    skipped = ComponentSizing("CHART-c", "Map", None, 6, 50, skipped="deck_scatter is not covered")
    report = SizingReport(1, (fits, cut, skipped))
    assert report.problems == [cut]
    assert report.summary().splitlines() == [
        "Campus: height 40, content 30-45 (recommended 31): ok",
        "Regions: height 10, content 30-45 (recommended 31): height 10 is below the content's minimum of 30 units",
        "Map: not checked (deck_scatter is not covered)",
    ]


def test_a_chart_whose_data_cannot_be_read_is_skipped_not_raised(monkeypatch):
    service = DashboardSizing(client=None)
    monkeypatch.setattr(service, "_chart_content",
                        lambda chart_id, title: (ChartShape.TABLE, "the chart data API refused its query (500)", 0))
    item = service._check_component("CHART-a", {"type": "CHART", "meta": {"chartId": 1, "width": 6, "height": 40}},
                                    calibrated_profile(), None, False)
    assert (item.shape, item.estimate, item.skipped) == (ChartShape.TABLE, None,
                                                         "the chart data API refused its query (500)")


def test_a_pivot_with_its_metrics_on_rows_shows_one_row_per_metric():
    params = {"groupbyRows": ["region"], "metrics": ["count", "sum__total", "avg__total"], "metricsLayout": "ROWS"}
    assert _pivot_content(params, RESULT, "").rows == 6  # 2 regions x 3 metrics
    assert _pivot_content({**params, "groupbyRows": []}, RESULT, "").rows == 3
    assert _pivot_content({**params, "metricsLayout": "COLUMNS"}, RESULT, "").rows == 2


def test_the_page_size_follows_the_table_plugin():
    # page_length stored as text (as in some example charts) is a number for Superset
    assert _table_content({"page_length": "5"}, RESULT, "").rows == 5
    assert _table_content({"page_length": "5"}, RESULT, "").pagination
    # without page_length, pagination starts above 5000 cells (200 rows per page)
    big = {"rowcount": 3000, "colnames": ["a", "b"], "data": []}
    assert (_table_content({}, big, "").rows, _table_content({}, big, "").pagination) == (200, True)
    assert _table_content({"page_length": 0}, RESULT, "").pagination is False


def test_a_table_with_totals_shows_one_more_row():
    assert _table_content({"show_totals": True}, RESULT, "").rows == 13
    assert _table_content({"show_totals": True, "query_mode": "raw"}, RESULT, "").rows == 12


def test_a_transposed_pivot_shows_its_column_dimensions_as_rows():
    params = {"groupbyRows": ["region"], "groupbyColumns": ["campus"], "transposePivot": True}
    assert _pivot_content(params, RESULT, "").rows == 12
    assert _pivot_content({**params, "transposePivot": False}, RESULT, "").rows == 2


def test_pivot_subtotals_add_a_row_per_partial_key():
    params = {"groupbyRows": ["region", "campus"], "rowSubTotals": True}
    assert _pivot_content(params, RESULT, "").rows == 12 + 2  # 12 leaves and a subtotal per region


def test_a_pivot_without_row_dimensions_shows_the_totals_row():
    assert _pivot_content({"groupbyColumns": ["region"]}, RESULT, "").rows == 1


def test_bars_of_a_legacy_chart_are_counted_on_its_migrated_x_axis():
    importlib.import_module("supersetapiplus.charts.echarts_timeseries_bar")
    chart = Chart.get_class("echarts_timeseries_bar", "supersetapiplus.charts.echarts_timeseries_bar").instance(
        slice_name="Monthly", datasource=DataSource(id=1, type="table"))
    chart.params.orientation = "horizontal"
    chart.params.granularity_sqla = "month"  # saved before x_axis existed
    chart.params.x_axis = None
    params = chart.explore_params()
    result = {"data": [{"month": f"2026-{m:02d}", "count": m} for m in range(1, 13)]}
    assert _bars_content(params, result, "").bars == 12

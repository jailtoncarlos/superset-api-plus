"""Content of a saved chart read from the chart data result (services.dashboard_sizing): pure logic, no HTTP. The
check against Superset is in tests/integration (test_dashboards.py and every example dashboard)."""
from supersetapiplus.dashboards.layout.sizing import ChartShape, SizingEstimate
from supersetapiplus.services.dashboard_sizing import (
    ComponentSizing,
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

"""Chart types whose dimensions or metrics live outside groupby/metrics: what the builder methods fill.

The params and query context of each type are checked against the UI captures in test_ui_defaults.py and
test_build_query.py; these tests cover the builder methods and the checks of charts built in code.
"""
import json

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.types import BigNumberAggregation, FunnelLabelType, HeatmapSortAxis
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.exceptions import ValidationError


def new_chart(viz_type: str) -> Chart:
    return Chart.for_viz_type(viz_type).instance(slice_name="new", datasource=DataSource(id=1, type="table"))


def sent(chart: Chart) -> tuple[dict, dict]:
    data = chart.to_json()
    return json.loads(data["params"]), json.loads(data["query_context"])


def test_bubble_metrics_fill_x_y_size_and_dimensions_fill_entity_then_series():
    chart = new_chart("bubble_v2")
    for metric in ("sum__a", "sum__b", "count"):
        chart.add_simple_metric(metric)
    chart.add_simple_dimension("country")
    chart.add_simple_dimension("region")

    params, context = sent(chart)

    assert (params["x"], params["y"], params["size"]) == ("sum__a", "sum__b", "count")
    assert (params["entity"], params["series"]) == ("country", "region")
    assert "metrics" not in params and "groupby" not in params
    (query,) = context["queries"]
    assert query["metrics"] == ["sum__a", "sum__b", "count"] and query["columns"] == ["country", "region"]


def test_bubble_takes_three_metrics_and_needs_all_of_them():
    chart = new_chart("bubble_v2")
    for metric in ("a", "b", "c"):
        chart.add_simple_metric(metric)
    with pytest.raises(ValidationError, match="three metrics"):
        chart.add_simple_metric("d")

    incomplete = new_chart("bubble_v2")
    incomplete.add_simple_metric("a")
    with pytest.raises(ValidationError, match="entity, y, size"):
        incomplete.to_json()


def test_sunburst_dimensions_build_the_columns_hierarchy():
    chart = new_chart("sunburst_v2")
    chart.add_simple_metric("count")
    chart.add_simple_dimension("region")
    chart.add_custom_dimension("upper", sql_expression="upper(city)")

    params, context = sent(chart)

    assert params["columns"][0] == "region" and params["columns"][1]["sqlExpression"] == "upper(city)"
    assert "groupby" not in params
    assert context["queries"][0]["columns"] == params["columns"]
    assert context["queries"][0]["orderby"] == [["count", False]]  # sort_by_metric of the automatic ordering


def test_histogram_bins_a_column_and_has_no_metric():
    chart = new_chart("histogram_v2")
    with pytest.raises(ValidationError, match="no metric"):
        chart.add_simple_metric("count")
    with pytest.raises(ValidationError, match="column"):
        chart.to_json()

    chart.set_column("total")
    chart.add_simple_dimension("campus")
    params, context = sent(chart)

    (query,) = context["queries"]
    assert params["column"] == "total" and "metrics" not in params and "metrics" not in query
    assert query["columns"] == ["campus", "total"]
    assert query["post_processing"] == [{"operation": "histogram", "options": {
        "column": "total", "groupby": ["campus"], "bins": 5, "cumulative": False, "normalize": False}}]


def test_heatmap_has_one_y_column_and_ranks_the_metric():
    chart = new_chart("heatmap_v2")
    chart.add_simple_metric("count")
    chart.set_x_axis("day")
    with pytest.raises(ValidationError, match="exactly one Y axis column"):
        chart.to_json()

    chart.add_simple_dimension("campus")
    chart.params.sort_y_axis = chart.query_context.form_data.sort_y_axis = HeatmapSortAxis.VALUE_DESC
    params, context = sent(chart)

    (query,) = context["queries"]
    assert "sort_by_metric" not in params
    assert query["columns"][0]["columnType"] == "BASE_AXIS" and query["columns"][1] == "campus"
    assert query["orderby"] == [["count", False]]
    assert query["post_processing"] == [{"operation": "rank", "options": {"metric": "count"}}]


@pytest.mark.parametrize("aggregation, queries", [(BigNumberAggregation.LAST_VALUE, 1), (BigNumberAggregation.RAW, 2)])
def test_big_number_trendline_adds_the_overall_value_query_for_raw(aggregation, queries):
    chart = new_chart("big_number")
    chart.add_simple_metric("count")
    with pytest.raises(ValidationError, match="x_axis"):
        chart.to_json()

    chart.set_x_axis("day")
    chart.params.aggregation = chart.query_context.form_data.aggregation = aggregation
    params, context = sent(chart)

    assert len(context["queries"]) == queries
    assert [rule["operation"] for rule in context["queries"][0]["post_processing"]] == ["pivot", "flatten"]
    assert "sort_by_metric" not in params
    with pytest.raises(ValidationError, match="no dimensions"):
        chart.add_simple_dimension("campus")


def test_funnel_label_types_are_sent_as_numbers():
    chart = new_chart("funnel")
    chart.add_simple_metric("count")
    chart.add_simple_dimension("stage")
    chart.params.label_type = chart.query_context.form_data.label_type = FunnelLabelType.KEY_VALUE

    params, _ = sent(chart)

    assert (params["label_type"], params["tooltip_label_type"]) == (3, 5)


@pytest.mark.parametrize("viz_type", ["echarts_timeseries_line", "echarts_area"])
def test_line_and_area_use_the_timeseries_query(viz_type):
    chart = new_chart(viz_type)
    chart.add_simple_metric("count")
    chart.set_x_axis("day")
    chart.add_simple_dimension("campus")

    _, context = sent(chart)

    (query,) = context["queries"]
    assert query["series_columns"] == ["campus"]
    # renameOperator: one metric split by a dimension is renamed to the dimension value (truncate_metric).
    assert [rule["operation"] for rule in query["post_processing"]] == ["pivot", "rename", "flatten"]

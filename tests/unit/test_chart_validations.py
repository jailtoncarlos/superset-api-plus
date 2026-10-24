"""Chart inputs rejected before reaching Superset, each rule from the Superset 6.1.0 source.

- removed viz types: superset/migrations/shared/migrate_viz/processors.py (and UPDATING.md #26328, filter_box);
- SQL metrics: superset/utils/core.py get_metric_name (without a label the result column is the SQL text);
- filter values: src/explore/constants.ts MULTI_OPERATORS / DISABLE_INPUT_OPERATORS, and
  superset/models/helpers.py filter_values_handler (a list on a single-value operator keeps its first item);
- box plot whiskers: plugin-chart-echarts BoxPlot buildQuery.ts PERCENTILE_REGEX and
  superset/utils/pandas_postprocessing/boxplot.py (low < high);
- time formats: d3-time-format (superset-ui-core/src/time-format), which prints moment.js tokens as text.
"""
import json

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import MetricHelper
from supersetapiplus.charts.types import FilterOperatorType, MetricType
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.exceptions import UnsupportedTypeError, ValidationError


def new_chart(viz_type: str) -> Chart:
    return Chart.for_viz_type(viz_type).instance(slice_name="c", datasource=DataSource(id=1, type="table"))


def adhoc_filters(chart: Chart) -> list:
    return json.loads(chart.to_json()["params"])["adhoc_filters"]


@pytest.mark.parametrize("viz_type, replacement", [("bar", "echarts_timeseries_bar"), ("dist_bar", "echarts_timeseries_bar"),
                                                   ("line", "echarts_timeseries_line"), ("area", "echarts_area")])
def test_removed_viz_type_names_its_replacement(viz_type, replacement):
    with pytest.raises(UnsupportedTypeError, match=f"was removed from Superset.*'{replacement}'"):
        Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")


def test_filter_box_points_to_native_filters_and_unknown_types_stay_unsupported():
    with pytest.raises(UnsupportedTypeError, match="native filters"):
        Chart.for_viz_type("filter_box")
    with pytest.raises(UnsupportedTypeError, match="is not supported by superset-api-plus"):
        Chart.for_viz_type("no_such_type")


def test_sql_metric_has_no_column_or_aggregate_and_needs_a_label():
    metric = MetricHelper.get_metric("Total", sql_expression="SUM(total)")
    assert (str(metric.expressionType), metric.aggregate, metric.column) == ("SQL", None, None)
    assert MetricHelper.get_metric("Rows").aggregate == MetricType.COUNT  # simple metric: COUNT by default

    with pytest.raises(ValidationError, match="neither a column nor an aggregate"):
        MetricHelper.get_metric("Total", sql_expression="SUM(total)", aggregate=MetricType.SUM)
    with pytest.raises(ValidationError, match="needs a label"):
        MetricHelper.get_metric("", sql_expression="SUM(total)")


def test_single_metric_chart_takes_a_sql_metric():
    chart = new_chart("big_number_total")

    chart.add_custom_metric("Total", sql_expression="SUM(total)")

    assert json.loads(chart.to_json()["params"])["metric"]["sqlExpression"] == "SUM(total)"


def test_filter_values_follow_the_operator():
    chart = new_chart("table")
    chart.add_simple_metric("count")
    chart.add_simple_filter("campus", "North", FilterOperatorType.IN)  # one value becomes a list
    chart.add_simple_filter("campus", ["North", "South"], FilterOperatorType.NOT_IN)
    chart.add_simple_filter("campus", operator=FilterOperatorType.IS_NULL)

    assert [f.get("comparator") for f in adhoc_filters(chart)] == [["North"], ["North", "South"], None]
    with pytest.raises(ValidationError, match="takes a single value"):
        chart.add_simple_filter("campus", ["North", "South"])
    with pytest.raises(ValidationError, match="takes no value"):
        chart.add_simple_filter("campus", "x", FilterOperatorType.IS_NOT_NULL)
    with pytest.raises(ValidationError, match="needs a value"):
        chart.add_simple_filter("campus", operator=FilterOperatorType.IN)


def test_box_plot_takes_custom_percentile_whiskers():
    chart = new_chart("box_plot")
    chart.params.set_whisker_percentiles(25, 75)
    assert chart.params.whiskerOptions == "25/75 percentiles"

    for invalid in ("75/25 percentiles", "1/200 percentiles", "quartiles"):
        chart.params.whiskerOptions = invalid
        with pytest.raises(ValidationError, match="Invalid whiskerOptions"):
            chart.params.validate()
    with pytest.raises(ValidationError):
        chart.params.set_whisker_percentiles(90, 10)


@pytest.mark.parametrize("value, valid", [("DD/MM/YYYY", False), ("YYYY-MM", False), ("%d/%m/%Y", True),
                                          ("%b %Y", True), ("smart_date", True)])
def test_time_formats_are_d3_patterns_not_moment_ones(value, valid):
    chart = new_chart("pie")
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    chart.params.date_format = value

    if valid:
        chart.params.validate()
    else:
        with pytest.raises(ValidationError, match="moment.js format"):
            chart.params.validate()


def test_time_format_of_a_chart_read_from_superset_is_written_back_as_read():
    params = {"datasource": "1__table", "viz_type": "pie", "metric": "count", "groupby": ["a"],
              "date_format": "DD/MM/YYYY"}
    chart = Chart.for_viz_type("pie").from_json({"id": 1, "slice_name": "p", "viz_type": "pie",
                                                  "params": json.dumps(params), "query_context": None})

    assert json.loads(chart.to_json()["params"])["date_format"] == "DD/MM/YYYY"

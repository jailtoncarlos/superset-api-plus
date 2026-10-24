"""Dimensions of charts created in code are stored in the control the UI uses for each viz_type."""
import importlib
import json

import pytest

from supersetapiplus.base.base import ObjectDecoder
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.exceptions import ValidationError


def new_chart(viz_type: str) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    return Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name="new", datasource=DataSource(id=1, type="table"))


def params(chart: Chart) -> dict:
    return json.loads(json.dumps(chart.params.to_dict(), cls=ObjectDecoder))


def test_custom_dimension_is_an_adhoc_column():
    chart = new_chart("table")

    chart.add_custom_dimension("Upper campus", sql_expression="upper(campus)")

    assert params(chart)["groupby"] == [
        {"expressionType": "SQL", "hasCustomLabel": True, "label": "Upper campus", "sqlExpression": "upper(campus)"}]


def test_aggregate_on_a_dimension_is_ignored_with_a_warning():
    chart = new_chart("table")

    with pytest.warns(DeprecationWarning):
        chart.add_custom_dimension("Campus", sql_expression="campus", aggregate="COUNT")
    assert "aggregate" not in params(chart)["groupby"][0]


def test_word_cloud_has_one_metric_and_its_dimension_in_series():
    chart = new_chart("word_cloud")

    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")

    data = params(chart)
    assert (data["metric"], data["series"], data["sort_by_metric"]) == ("count", "campus", True)
    assert "groupby" not in data
    with pytest.raises(ValidationError):
        chart.add_simple_dimension("other")


def test_big_number_has_one_metric_and_no_dimension():
    chart = new_chart("big_number_total")

    chart.add_simple_metric("count")

    data = params(chart)
    assert data["metric"] == "count" and "groupby" not in data and "sort_by_metric" not in data
    with pytest.raises(ValidationError):
        chart.add_simple_dimension("campus")


def test_bar_y_axis_is_deprecated_and_sets_the_x_axis():
    chart = new_chart("echarts_timeseries_bar")

    with pytest.warns(DeprecationWarning):
        chart.y_axis("Campus", sql_expression="campus")

    assert params(chart)["x_axis"] == {"expressionType": "SQL", "hasCustomLabel": True, "label": "Campus",
                                       "sqlExpression": "campus"}


def test_box_plot_distributes_across_columns_without_requiring_dimensions():
    chart = new_chart("box_plot")

    chart.add_simple_metric("count")
    chart.add_distribute_across("day")

    assert params(chart)["columns"] == ["day"]
    chart.params.validate()

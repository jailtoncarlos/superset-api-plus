"""set_x_axis of the charts with an X axis control on a chart read from Superset without a stored query_context
(issue #149): the params get the axis, and the form_data too when there is a query context. Pure logic, no HTTP."""
import json

import pytest

from supersetapiplus.charts.charts import Chart

VIZ_TYPES = ["echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area", "mixed_timeseries", "big_number",
             "heatmap_v2", "echarts_timeseries_scatter"]


def read_chart(viz_type: str, with_query_context: bool) -> Chart:
    params = {"datasource": "1__table", "viz_type": viz_type, "metrics": ["count"]}
    query_context = None if not with_query_context else json.dumps({
        "datasource": {"id": 1, "type": "table"}, "force": False, "queries": [], "form_data": params,
        "result_format": "json", "result_type": "full"})
    return Chart.for_viz_type(viz_type).from_json({
        "id": 1, "slice_name": "c", "viz_type": viz_type, "datasource_id": 1, "datasource_type": "table",
        "params": json.dumps(params), "query_context": query_context})


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_the_x_axis_of_a_chart_read_without_a_query_context_is_set_on_the_params(viz_type):
    chart = read_chart(viz_type, with_query_context=False)

    chart.set_x_axis("order_date")

    assert chart.params.x_axis == "order_date" and chart.query_context is None


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_the_x_axis_of_a_chart_read_with_a_query_context_is_set_on_both(viz_type):
    chart = read_chart(viz_type, with_query_context=True)

    chart.set_x_axis("order_date")

    assert chart.params.x_axis == chart.query_context.form_data.x_axis == "order_date"

"""Custom ECharts options (`echart_options`) of the timeseries charts: the field, its default and the checks
ported from the Superset 6.1.0 frontend (supersetapiplus.charts.echart_options). Pure logic, no HTTP."""
import json

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.echart_options import echart_options_text
from supersetapiplus.exceptions import ValidationError

WITH_CONTROL = ["echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area", "mixed_timeseries"]
STACKED_LABELS = {"legend": {"show": False}, "yAxis": {"axisLabel": {"color": "#666"}}}


def new_chart(viz_type: str) -> Chart:
    return Chart.for_viz_type(viz_type)(slice_name="new", datasource_id=1)


def read_chart(viz_type: str, params: dict, form_data: dict | None = None) -> Chart:
    """A chart as read from Superset (GET /chart/{id}), with a stored query_context when `form_data` is given."""
    params = {"datasource": "1__table", "viz_type": viz_type, **params}
    query_context = None if form_data is None else json.dumps({
        "datasource": {"id": 1, "type": "table"}, "force": False, "queries": [],
        "form_data": {"datasource": "1__table", "viz_type": viz_type, **form_data},
        "result_format": "json", "result_type": "full"})
    return Chart.for_viz_type(viz_type).from_json({
        "id": 1, "slice_name": "c", "viz_type": viz_type, "datasource_id": 1, "datasource_type": "table",
        "params": json.dumps(params), "query_context": query_context})


@pytest.mark.parametrize("viz_type", WITH_CONTROL)
def test_set_echart_options_writes_the_json_text_in_params_and_form_data(viz_type):
    chart = new_chart(viz_type)
    assert chart.params.echart_options == "{}"  # the control default, as Explore gives a new chart

    chart.set_echart_options(STACKED_LABELS)

    assert json.loads(chart.params.echart_options) == STACKED_LABELS
    assert chart.ui_query_context()["form_data"]["echart_options"] == chart.params.echart_options
    chart.params.validate()


def test_options_are_set_on_the_form_data_of_a_chart_read_from_superset():
    chart = read_chart("echarts_timeseries_bar", {"metrics": ["count"]}, form_data={"metrics": ["count"]})

    chart.set_echart_options({"legend": {"show": False}})

    assert chart.params.echart_options == chart.query_context.form_data.echart_options == '{"legend": {"show": false}}'


def test_empty_options_clear_the_override():
    chart = new_chart("echarts_timeseries_line")
    chart.set_echart_options(STACKED_LABELS)

    chart.set_echart_options(None)

    assert chart.params.echart_options == "{}"


@pytest.mark.parametrize("stored", ["{}", '{ title: { text: "My Chart" } }', "", None])
def test_a_chart_read_from_superset_writes_echart_options_back_as_read(stored):
    chart = read_chart("echarts_timeseries_line", {"echart_options": stored})

    written = json.loads(chart.to_json()["params"])

    assert written["echart_options"] == stored
    chart.params.validate()  # what Superset stored is not checked


def test_absent_echart_options_stays_absent():
    chart = read_chart("echarts_area", {"metrics": ["count"]})

    assert "echart_options" not in json.loads(chart.to_json()["params"])


def test_keys_the_frontend_drops_are_rejected():
    with pytest.raises(ValidationError, match=r"\['labels'\] are not accepted"):
        echart_options_text({"labels": {"show": True}, "legend": {}})


def test_functions_are_rejected_as_the_frontend_parser_does():
    with pytest.raises(ValidationError, match="series.label.formatter is a function"):
        echart_options_text({"series": {"label": {"formatter": lambda value: value}}})


def test_static_values_are_written_as_json():
    text = echart_options_text({"backgroundColor": "#fff", "darkMode": "auto", "animation": False,
                                "grid": [{"top": 10}, {"top": "50%"}], "title": {"text": "Ação"}})
    assert json.loads(text)["title"]["text"] == "Ação" and '"Ação"' in text


def test_a_chart_built_in_code_needs_json_in_echart_options():
    chart = new_chart("echarts_timeseries_bar")
    chart.params.echart_options = "{ legend: { show: false } }"
    with pytest.raises(ValidationError, match="JSON text of an object"):
        chart.params.validate()

    chart.params.echart_options = '{"label": {}}'
    with pytest.raises(ValidationError, match="not accepted"):
        chart.params.validate()

    chart.params.echart_options = '[1]'
    with pytest.raises(ValidationError, match="must be an object"):
        chart.params.validate()

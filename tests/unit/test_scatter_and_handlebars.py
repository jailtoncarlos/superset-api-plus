"""Scatter plot (echarts_timeseries_scatter) and handlebars charts built in code, and the formula annotation layers of
the timeseries charts: the query each one derives is the one Explore sent for the same chart
(tests/fixtures/ui_query_contexts_6.1.0, captured by bin/scripts/extract_query_contexts.py), and the layers have the
shape the Explore annotation popover saves (AnnotationLayer.tsx). Pure logic, no HTTP."""
import json
from pathlib import Path

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.echarts_timeseries_scatter import EchartsTimeseriesScatterChart
from supersetapiplus.charts.explore import DatasetTime
from supersetapiplus.charts.handlebars import DEFAULT_TEMPLATE, HandlebarsChart
from supersetapiplus.charts.timeseries import formula_annotation_layer
from supersetapiplus.charts.types import AnnotationStyle, QueryModeType, TimeGrain
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.exceptions import ValidationError

CAPTURES = Path(__file__).parent.parent / "fixtures" / "ui_query_contexts_6.1.0"
SALES = DatasetTime(columns=("order_date",), main="order_date")


def captured_queries(name: str) -> list:
    return json.loads((CAPTURES / f"{name}.json").read_text())["queries"]


def derived_queries(chart: Chart) -> list:
    return [{k: v for k, v in query.items() if k != "url_params"} for query in chart.ui_query_context()["queries"]]


def new_chart(chart_class: type[Chart]) -> Chart:
    chart = chart_class.instance(slice_name="new", datasource=DataSource(id=1, type="table"))
    chart.use_dataset_time(SALES)
    return chart


def test_scatter_with_a_formula_reference_line_sends_the_query_explore_sent():
    chart = new_chart(EchartsTimeseriesScatterChart)
    chart.add_simple_metric("count")
    chart.set_x_axis("order_date")
    chart.params.time_grain_sqla = TimeGrain.MONTH
    chart.params.markerEnabled = True
    chart.add_formula_annotation("Upper limit", "3000", style=AnnotationStyle.DASHED, width=2, show_label=True)

    assert derived_queries(chart) == captured_queries("echarts_timeseries_scatter_formula_annotation")


def test_formula_layer_has_the_fields_the_explore_popover_saves():
    (captured,) = captured_queries("echarts_timeseries_scatter_formula_annotation")[0]["annotation_layers"]

    layer = formula_annotation_layer("Upper limit", "3000", AnnotationStyle.DASHED, width=2, show_label=True)

    assert layer == captured
    assert json.loads(json.dumps(layer)) == captured  # plain JSON values (enums written as their value)


def test_a_layer_with_the_same_name_is_replaced_and_form_data_follows_params():
    chart = new_chart(EchartsTimeseriesScatterChart)

    chart.add_formula_annotation("Mean", "100")
    chart.add_formula_annotation("Upper limit", "130", color="#d62728")
    chart.add_formula_annotation("Mean", "110")

    assert [(layer["name"], layer["value"]) for layer in chart.params.annotation_layers] == [
        ("Upper limit", "130"), ("Mean", "110")]
    assert chart.query_context.form_data.annotation_layers == chart.params.annotation_layers


@pytest.mark.parametrize(("name", "formula"), [("", "1"), ("Limit", " ")])
def test_a_formula_layer_needs_a_name_and_a_formula(name, formula):
    with pytest.raises(ValidationError, match="needs a name and a formula"):
        formula_annotation_layer(name, formula)


@pytest.mark.parametrize("viz_type", ["echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area"])
def test_the_other_timeseries_charts_take_formula_layers(viz_type):
    chart = Chart.for_viz_type(viz_type)(slice_name="new", datasource_id=1)

    chart.add_formula_annotation("Target", "50")

    assert chart.ui_query_context()["queries"][0]["annotation_layers"][0]["value"] == "50"


def test_handlebars_in_aggregate_mode_sends_the_query_explore_sent():
    chart = new_chart(HandlebarsChart)
    chart.add_simple_metric("count")
    chart.add_simple_dimension("product_line")
    chart.params.timeseries_limit_metric = "count"
    chart.params.row_limit = 10
    chart.set_template("<ul>{{#each data}}<li>{{product_line}}: {{count}}</li>{{/each}}</ul>")

    assert derived_queries(chart) == captured_queries("handlebars")


def test_handlebars_raw_columns_switch_to_a_raw_query_without_metrics():
    chart = new_chart(HandlebarsChart)
    chart.add_raw_column("order_number")
    chart.add_raw_column("product_line")
    chart.set_template("{{#each data}}{{order_number}} {{/each}}", style=".x { color: red; }")

    (query,) = chart.ui_query_context()["queries"]

    assert query["columns"] == ["order_number", "product_line"] and "metrics" not in query
    assert chart.params.query_mode == QueryModeType.RAW and chart.params.styleTemplate == ".x { color: red; }"
    assert chart.query_context.form_data.all_columns == chart.params.all_columns
    chart.params.validate()


def test_handlebars_built_in_code_is_checked_as_the_control_panel_does():
    chart = new_chart(HandlebarsChart)
    assert chart.params.handlebarsTemplate == DEFAULT_TEMPLATE
    with pytest.raises(ValidationError, match="Group By, Metrics or Percentage Metrics"):
        chart.params.validate()

    chart.add_simple_metric("count")
    chart.set_template("  ")
    with pytest.raises(ValidationError, match="handlebarsTemplate cannot be empty"):
        chart.params.validate()


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


@pytest.mark.parametrize("params", [{}, {"handlebarsTemplate": None}, {"handlebarsTemplate": ""},
                                    {"query_mode": "aggregate", "metrics": [], "groupby": []}])
def test_a_handlebars_chart_read_from_superset_is_written_back_as_read(params):
    chart = read_chart("handlebars", params)

    written = json.loads(chart.to_json()["params"])

    assert {key: written.get(key, "<absent>") for key in params} == params


def test_a_formula_layer_is_added_to_a_chart_read_without_annotation_layers():
    chart = read_chart("echarts_timeseries_scatter", {"metrics": ["count"]}, form_data={"metrics": ["count"]})

    chart.add_formula_annotation("Limit", "10")

    assert [layer["value"] for layer in chart.params.annotation_layers] == ["10"]
    assert chart.query_context.form_data.annotation_layers == chart.params.annotation_layers


def test_a_raw_column_is_added_to_a_handlebars_chart_read_without_all_columns():
    chart = read_chart("handlebars", {"metrics": ["count"]}, form_data={"metrics": ["count"]})

    chart.add_raw_column("campus")

    assert chart.params.all_columns == chart.query_context.form_data.all_columns == ["campus"]

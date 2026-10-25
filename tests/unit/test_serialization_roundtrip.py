"""Chart round trip (from_json -> to_json) with payloads in the format exported by Superset.

The payloads are synthetic but reproduce situations found in real dashboards: null
query_context, keys not modeled by the library and mismatches that Superset itself keeps
between params and query_context.form_data.
"""
import importlib
import json

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.exceptions import ValidationError

DATASOURCE = "1__table"

METRIC_COUNT_DISTINCT = {
    "aggregate": "COUNT_DISTINCT",
    "column": {"column_name": "respondent_id", "type": "INTEGER", "filterable": True, "groupby": True},
    "expressionType": "SIMPLE",
    "hasCustomLabel": True,
    "label": "Respondents",
    "optionName": "metric_abc",
    "sqlExpression": None,
}


def load_chart(viz_type: str, params: dict, query_context=None, chart_id: int = 10) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")
    data = {
        "id": chart_id,
        "slice_name": f"chart {viz_type}",
        "viz_type": viz_type,
        "params": json.dumps(params),
        "query_context": json.dumps(query_context) if query_context is not None else None,
    }
    return chart_class.from_json(data)


def dumped(chart: Chart, field_name: str):
    value = chart.to_json()[field_name]
    return json.loads(value) if isinstance(value, str) else value


def word_cloud_params() -> dict:
    return {
        "datasource": DATASOURCE,
        "viz_type": "word_cloud",
        "series": "word",
        "metric": METRIC_COUNT_DISTINCT,
        "adhoc_filters": [],
        "row_limit": 100,
        "size_from": 12,
        "size_to": 70,
        "rotation": "square",
        "color_scheme": "presetColors",
        "extra_form_data": {},
        "dashboards": [3],
    }


def test_preserves_unmodeled_keys_in_params():
    chart = load_chart("word_cloud", word_cloud_params())

    params = dumped(chart, "params")

    for key in ("series", "metric", "rotation", "size_from", "size_to", "color_scheme"):
        assert params[key] == word_cloud_params()[key], key


def test_null_query_context_is_preserved_and_datasource_comes_from_params():
    chart = load_chart("word_cloud", word_cloud_params(), query_context=None)

    assert chart.query_context is None
    assert chart.datasource_id == 1
    assert dumped(chart, "query_context") is None


def test_mismatched_slice_id_and_request_parameters_are_tolerated():
    params = {
        "datasource": DATASOURCE,
        "viz_type": "table",
        "query_mode": "aggregate",
        "groupby": ["uo_nome"],
        "metrics": [METRIC_COUNT_DISTINCT],
        "slice_id": 366,
    }
    form_data = dict(params, slice_id=1135, force=False, result_format="json", result_type="full")
    query_context = {
        "datasource": {"id": 1, "type": "table"},
        "force": False,
        "queries": [{"columns": ["uo_nome"], "metrics": [METRIC_COUNT_DISTINCT], "filters": []}],
        "form_data": form_data,
        "result_format": "json",
        "result_type": "full",
    }

    chart = load_chart("table", params, query_context)

    assert dumped(chart, "params")["slice_id"] == 366
    assert dumped(chart, "query_context")["form_data"]["slice_id"] == 1135


def test_form_data_with_legacy_none_datasource_is_tolerated():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": ["uo_nome"], "metrics": [METRIC_COUNT_DISTINCT]}
    query_context = {
        "datasource": {"id": 1, "type": "table"},
        "queries": [{"columns": ["uo_nome"], "metrics": [METRIC_COUNT_DISTINCT], "filters": []}],
        "form_data": dict(params, datasource="None__table"),
    }

    chart = load_chart("table", params, query_context)

    assert dumped(chart, "params")["datasource"] == DATASOURCE


def mixed_timeseries_payload(form_data_b: dict) -> tuple:
    params = {"datasource": DATASOURCE, "viz_type": "mixed_timeseries", "x_axis": "ano",
              "metrics": [METRIC_COUNT_DISTINCT], "groupby": [],
              "metrics_b": [METRIC_COUNT_DISTINCT], "groupby_b": ["uo_nome"], "row_limit_b": 100}
    form_data = {k: v for k, v in params.items() if not k.endswith("_b")}
    form_data.update(form_data_b)
    query_context = {
        "datasource": {"id": 1, "type": "table"},
        "queries": [{"columns": ["ano"], "metrics": [METRIC_COUNT_DISTINCT], "filters": []}],
        "form_data": form_data,
    }
    return params, query_context


def test_mixed_timeseries_without_query_b_keys_in_form_data_is_tolerated():
    params, query_context = mixed_timeseries_payload({})

    chart = load_chart("mixed_timeseries", params, query_context)

    assert dumped(chart, "params")["groupby_b"] == ["uo_nome"]
    assert "groupby_b" not in dumped(chart, "query_context")["form_data"]


def test_mixed_timeseries_with_mismatched_query_b_is_still_rejected():
    params, query_context = mixed_timeseries_payload({"row_limit_b": 500})

    chart = load_chart("mixed_timeseries", params, query_context)

    with pytest.raises(ValidationError):
        chart.to_json()


def test_real_mismatch_between_params_and_form_data_is_still_rejected():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": ["uo_nome"], "metrics": [METRIC_COUNT_DISTINCT], "row_limit": 10}
    query_context = {
        "datasource": {"id": 1, "type": "table"},
        "queries": [{"columns": ["uo_nome"], "metrics": [METRIC_COUNT_DISTINCT], "filters": []}],
        "form_data": dict(params, row_limit=500),
    }

    chart = load_chart("table", params, query_context)

    with pytest.raises(ValidationError):
        chart.to_json()


def test_aggregate_table_with_only_dimensions_is_valid():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": [{"expressionType": "SQL", "label": "Answers", "sqlExpression": "(answer_value)"}],
              "metrics": [], "percent_metrics": []}

    chart = load_chart("table", params)

    assert dumped(chart, "params")["groupby"] == params["groupby"]


def test_raw_table_without_metrics_is_valid():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "raw",
              "all_columns": ["uo_nome", "curso"], "metrics": []}

    chart = load_chart("table", params)

    assert dumped(chart, "params")["all_columns"] == ["uo_nome", "curso"]


def test_table_without_metrics_or_dimensions_is_invalid():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": [], "metrics": [], "percent_metrics": []}

    chart = load_chart("table", params)

    with pytest.raises(ValidationError):
        chart.to_json()


def test_comparing_different_classes_neither_fails_nor_changes_objects():
    chart = load_chart("word_cloud", word_cloud_params())
    extra_before = dict(chart.params.extra_fields)

    assert (chart.params != object()) is True
    assert chart.params == chart.params
    assert chart.params.extra_fields == extra_before


def test_null_query_context_is_written_as_null_not_as_text():
    chart = load_chart("word_cloud", word_cloud_params(), query_context=None)

    assert chart.to_json()["query_context"] is None


def test_query_context_stored_as_text_null_is_read_as_none():
    importlib.import_module("supersetapiplus.charts.pie")
    chart_class = Chart.get_class("pie", "supersetapiplus.charts.pie")
    params = {"datasource": DATASOURCE, "viz_type": "pie", "groupby": ["campus"], "metric": "count"}

    chart = chart_class.from_json({"id": 3, "slice_name": "p", "viz_type": "pie",
                                   "params": json.dumps(params), "query_context": "null"})

    assert chart.query_context is None


def test_top_level_response_datasource_takes_precedence_over_params():
    params = dict(word_cloud_params(), datasource="42__table")
    importlib.import_module("supersetapiplus.charts.word_cloud")
    chart_class = Chart.get_class("word_cloud", "supersetapiplus.charts.word_cloud")

    chart = chart_class.from_json({"id": 3, "slice_name": "w", "viz_type": "word_cloud", "params": json.dumps(params),
                                   "query_context": None, "datasource_id": 10, "datasource_type": "table"})

    assert chart.datasource_id == 10


@pytest.mark.parametrize("viz_type,params", [
    ("pie", {"viz_type": "pie", "groupby": ["campus"], "metric": "count"}),
    ("cal_heatmap", {"viz_type": "cal_heatmap", "metrics": ["count"]}),
])
def test_new_chart_created_by_from_json_receives_the_datasource(viz_type, params):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")

    chart = chart_class.from_json({"id": None, "slice_name": "new", "viz_type": viz_type, "params": json.dumps(params),
                                   "query_context": None, "datasource_id": 29, "datasource_type": "table"})

    assert chart.params.datasource == "29__table"
    assert chart.query_context is None
    assert json.loads(chart.to_json()["params"])["datasource"] == "29__table"


def test_chart_whose_stored_form_data_lacks_a_params_key_is_written_back():
    # Older Superset versions stored query_context.form_data without some params keys (annotation_layers).
    params = {"datasource": DATASOURCE, "viz_type": "big_number_total", "metric": "count", "annotation_layers": []}
    query_context = {"datasource": {"id": 1, "type": "table"}, "queries": [{"metrics": ["count"]}],
                     "form_data": {k: v for k, v in params.items() if k != "annotation_layers"}}

    chart = load_chart("big_number_total", params, query_context)

    assert dumped(chart, "params") == params
    assert dumped(chart, "query_context") == query_context


def test_table_query_saved_without_ordering_or_metrics_is_written_back():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "raw", "all_columns": ["name"]}
    query_context = {"datasource": {"id": 1, "type": "table"},
                     "queries": [{"columns": ["name"], "metrics": [], "orderby": []}], "form_data": params}

    chart = load_chart("table", params, query_context)

    assert dumped(chart, "query_context")["queries"] == query_context["queries"]


def test_query_context_of_a_saved_chart_targets_its_dataset_not_the_stale_params_datasource():
    """Issue #19: the Superset examples store a stale params.datasource (chart on dataset 20, params "21__table").
    Superset builds the form_data of a saved chart with its own datasource (Slice.form_data, models/slice.py)."""
    params = dict(word_cloud_params(), datasource="21__table")
    importlib.import_module("supersetapiplus.charts.word_cloud")
    chart = Chart.get_class("word_cloud", "supersetapiplus.charts.word_cloud").from_json(
        {"id": 5, "slice_name": "w", "viz_type": "word_cloud", "params": json.dumps(params), "query_context": None,
         "datasource_id": 20, "datasource_type": "table"})

    context = chart.ui_query_context()

    assert context["datasource"] == {"id": 20, "type": "table"}
    assert context["form_data"]["datasource"] == "20__table"
    assert json.loads(chart.to_json()["params"])["datasource"] == "21__table"  # params written back as read

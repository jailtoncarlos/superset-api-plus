"""The params of a chart normalized as Explore does before buildQuery (supersetapiplus/charts/explore.py).

References, both captured from Explore on the test stack with the examples (never built by the library):

- tests/fixtures/example_query_contexts_6.1.0.json: for each example chart, the params Superset stores, the temporal
  columns of its dataset and the queries Explore sends (bin/scripts/extract_example_query_contexts.py);
- tests/fixtures/ui_controls_6.1.0.json: the keys read by buildQuery that are controls of each viz_type
  (bin/scripts/extract_ui_controls.py).

Each issue fixed here has a test built on a chart read from Superset with legacy or incomplete params.
"""
import copy
import json
from pathlib import Path

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.explore import PROBED_KEYS, QUERY_CONTROLS, DatasetTime, explore_form_data
from tests.integration.test_examples.references import portable

FIXTURES = Path(__file__).parent.parent / "fixtures"
CAPTURES = json.loads((FIXTURES / "example_query_contexts_6.1.0.json").read_text())["charts"]
CONTROLS = json.loads((FIXTURES / "ui_controls_6.1.0.json").read_text())


def read_chart(params: dict, viz_type: str | None = None) -> Chart:
    """A chart as read from Superset (GET /chart/{id}) with these params."""
    viz_type = viz_type or params["viz_type"]
    return Chart.for_viz_type(viz_type).from_json({
        "id": 1, "slice_name": "c", "viz_type": viz_type, "datasource_id": 1, "datasource_type": "table",
        "params": json.dumps({"datasource": "1__table", "viz_type": viz_type, **params}), "query_context": None})


def queries(context: dict) -> list[dict]:
    return [{key: value for key, value in portable(query).items() if key != "url_params"}
            for query in context["queries"]]


def test_controls_are_the_captured_ones():
    assert PROBED_KEYS == set(CONTROLS["probed"])
    assert {viz: sorted(keys) for viz, keys in QUERY_CONTROLS.items()} == CONTROLS["controls"]


@pytest.mark.parametrize("uuid", sorted(CAPTURES), ids=lambda uuid: f"{CAPTURES[uuid]['viz_type']}-{uuid[:8]}")
def test_example_chart_builds_the_queries_of_explore(uuid):
    capture = CAPTURES[uuid]
    chart = read_chart(copy.deepcopy(capture["params"]), capture["viz_type"])
    chart._dataset_time = DatasetTime(tuple(capture["dataset_time"]["columns"]), capture["dataset_time"]["main"])

    assert queries(chart.ui_query_context()) == queries(capture["query_context"])


def test_form_data_of_the_context_stays_the_stored_params():
    params = {"metric": "count", "groupby": ["a"], "since": "2000-01-01", "until": "now", "limit": 5}
    chart = read_chart({**params, "viz_type": "pie"})

    context = chart.ui_query_context()

    assert {key: context["form_data"][key] for key in params} == params
    assert {"since", "until", "time_range", "series_limit"} & set(context["queries"][0]) == {"series_limit"}


def test_legacy_since_until_become_the_time_range():
    """Issue #23: the stale range was sent instead of since/until (superset/legacy.py update_time_range); the range
    applies to the time filter of the chart (merge_extra_filters, superset/utils/core.py)."""
    time_filter = {"clause": "WHERE", "subject": "year", "operator": "TEMPORAL_RANGE", "comparator": "2014 : 2015",
                   "expressionType": "SIMPLE"}
    chart = read_chart({"viz_type": "treemap_v2", "metric": "count", "groupby": ["a"], "time_range": "Last year",
                        "since": "1960-01-01", "until": "now", "adhoc_filters": [time_filter]})

    query = chart.ui_query_context()["queries"][0]

    assert query["filters"] == [{"col": "year", "op": "TEMPORAL_RANGE", "val": "1960-01-01 : now"}]
    assert "time_range" not in query  # not a control of the treemap: Explore leaves it out


@pytest.mark.parametrize("params, key, expected", [
    ({"viz_type": "pie", "metric": "count", "groupby": ["a"]}, "orderby", [["count", False]]),  # sort_by_metric
    ({"viz_type": "table", "metrics": ["count"], "groupby": ["a"], "timeseries_limit_metric": "count"},
     "orderby", [["count", False]]),  # order_desc
    ({"viz_type": "table", "metrics": ["count"], "groupby": ["a"], "row_limit": None}, "row_limit", 10000),
])
def test_absent_or_null_controls_take_their_default(params, key, expected):
    """Issue #24: getControlState.ts gives the control default to a null or absent stored value."""
    assert read_chart(params).ui_query_context()["queries"][0][key] == expected


def test_box_plot_without_whiskers_gets_the_tukey_statistics():
    """Issue #24: without whiskerOptions the box plot returned the raw rows instead of the statistics."""
    chart = read_chart({"viz_type": "box_plot", "metrics": ["count"], "columns": ["a"], "groupby": ["b"]})

    assert chart.ui_query_context()["queries"][0]["post_processing"][0]["options"]["whisker_type"] == "tukey"


def test_stored_keys_that_are_not_controls_are_not_sent():
    """Issue #25: a leftover granularity_sqla became the query granularity (year read as epoch milliseconds), and a
    leftover limit the series limit of a chart without that control."""
    table = read_chart({"viz_type": "table", "metrics": ["count"], "groupby": ["year"], "granularity_sqla": "year"})
    pie = read_chart({"viz_type": "pie", "metric": "count", "groupby": ["a"], "limit": 25})

    assert "granularity" not in table.ui_query_context()["queries"][0]
    assert pie.ui_query_context()["queries"][0]["series_limit"] == 0


def test_legacy_time_column_becomes_the_x_axis():
    """Issue #26: xAxisMixin (mixins.tsx) moves granularity_sqla to the x axis; the query had __timestamp."""
    chart = read_chart({"viz_type": "echarts_timeseries_line", "metrics": ["count"], "groupby": [],
                        "granularity_sqla": "ds", "time_range": "No filter"})

    query = chart.ui_query_context()["queries"][0]

    assert query["columns"][0]["sqlExpression"] == "ds" and query["columns"][0]["columnType"] == "BASE_AXIS"
    assert "is_timeseries" not in query
    assert query["filters"] == [{"col": "ds", "op": "TEMPORAL_RANGE", "val": "No filter"}]


def test_controls_explore_takes_from_the_dataset():
    """The temporal lookup is recomputed from the dataset (issue #28, item 1) and the box plot takes its default
    temporal column; without the dataset the stored values are kept."""
    params = {"viz_type": "box_plot", "metrics": ["count"], "groupby": ["region"], "whiskerOptions": "Tukey",
              "temporal_columns_lookup": {"stale": True}}
    dataset = DatasetTime(columns=("day", "year"), main="year")

    explored = explore_form_data(params, {}, dataset)

    assert explored["temporal_columns_lookup"] == {"day": True, "year": True}
    assert explored["columns"] == ["year"]
    assert explore_form_data(params, {})["temporal_columns_lookup"] == {"stale": True}

"""Charts against the real Superset: search, reading, writing, data, export and import."""
import importlib
import json
import zipfile

import pytest

from supersetapiplus.resources.repository import UnsupportedObject
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.exceptions import (
    BadRequestError,
    MultipleFound,
    NotFound,
    ResourceNotFoundError,
    UnsupportedTypeError,
)
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

from .conftest import name_filter, new_chart, unique_name


@pytest.fixture
def three_tables(add_chart):
    """Three table charts sharing a unique prefix (slice names <prefix>-0..2)."""
    prefix = unique_name("find")
    charts = [add_chart("table", f"{prefix}-{i}") for i in range(3)]
    return prefix, charts


# --- Search ----------------------------------------------------------------------------------

def test_find_filters_paginates_and_returns_typed_charts(client, three_tables):
    prefix, charts = three_tables
    query_filter = name_filter("slice_name", prefix, QueryOperator.STARTS_WITH)

    first = client.charts.find(query_filter, page_size=2, page=0, order_column="slice_name", order_direction="asc")
    second = client.charts.find(query_filter, page_size=2, page=1, order_column="slice_name", order_direction="asc")

    assert (len(first), len(second)) == (2, 1)
    assert [c.slice_name for c in first + second] == [c.slice_name for c in charts]
    assert all(type(c).__name__ == "TableChart" and isinstance(c, Chart) for c in first + second)


def test_find_sorts_descending(client, three_tables):
    prefix, charts = three_tables

    found = client.charts.find(name_filter("slice_name", prefix, QueryOperator.STARTS_WITH), columns=["id"],
                               order_column="slice_name", order_direction="desc")

    assert [c.id for c in found] == [c.id for c in reversed(charts)]


def test_find_with_restricted_columns_returns_partial_objects(client, three_tables):
    prefix, charts = three_tables

    found = client.charts.find(name_filter("slice_name", prefix, QueryOperator.STARTS_WITH),
                               columns=["id", "slice_name", "viz_type"])

    assert sorted(c.id for c in found) == sorted(c.id for c in charts)


def test_count_and_find_all_follow_the_filter(client, three_tables):
    prefix, charts = three_tables
    query_filter = name_filter("slice_name", prefix, QueryOperator.STARTS_WITH)

    pages = []
    original_find = client.charts.find

    def recording_find(*args, **kwargs):
        result = original_find(*args, **kwargs)
        pages.append(len(result))
        return result

    client.charts.find = recording_find
    try:
        found = client.charts.find_all(query_filter, columns=["id", "viz_type"], page_size=2)
    finally:
        del client.charts.find

    assert client.charts.count(query_filter) == 3
    assert pages == [2, 1], "find_all walks the pages the server returns"
    assert sorted(c.id for c in found) == sorted(c.id for c in charts)


def test_find_one_not_found_multiple_and_full(client, three_tables):
    prefix, charts = three_tables

    with pytest.raises(NotFound):
        client.charts.find_one(name_filter("slice_name", unique_name("missing")))
    with pytest.raises(MultipleFound):
        client.charts.find_one(name_filter("slice_name", prefix, QueryOperator.STARTS_WITH))

    columns = ["id", "slice_name", "viz_type"]
    partial = client.charts.find_one(name_filter("slice_name", charts[0].slice_name), columns=columns)
    full = client.charts.find_one(name_filter("slice_name", charts[0].slice_name), columns=columns, full=True)
    assert partial.id == full.id == charts[0].id
    # The restricted listing does not bring params (the partial object keeps them as an empty dict).
    assert not (partial.params if isinstance(partial.params, dict) else partial.params.to_dict()).get("groupby")
    assert full.params.groupby == ["campus"] and full.query_context is not None


def test_listing_tolerates_an_unmodeled_viz_type(client, unmodeled_chart, three_tables):
    query_filter = QueryStringFilter()
    query_filter.add("id", QueryOperator.IN, [unmodeled_chart, three_tables[1][0].id])

    found = {c.id: c for c in client.charts.find(query_filter, columns=["id", "slice_name", "viz_type"])}

    assert isinstance(found[unmodeled_chart], UnsupportedObject)
    assert type(found[three_tables[1][0].id]).__name__ == "TableChart"


# --- Reading ---------------------------------------------------------------------------------

@pytest.mark.parametrize("viz_type,class_name", [("table", "TableChart"), ("pie", "PieChart")])
def test_get_resolves_the_class_from_viz_type(client, add_chart, viz_type, class_name):
    chart = add_chart(viz_type)

    assert type(client.charts.get(chart.id)).__name__ == class_name


def test_get_of_unmodeled_viz_type_raises_unsupported_type(client, unmodeled_chart):
    with pytest.raises(UnsupportedTypeError):
        client.charts.get(unmodeled_chart)


# --- Writing ---------------------------------------------------------------------------------

@pytest.mark.parametrize("viz_type", ["table", "pie", "treemap_v2", "funnel", "gauge_chart", "sunburst_v2"])
def test_chart_created_in_code_round_trips(client, dataset, add_chart, viz_type):
    chart = add_chart(viz_type)

    fetched = client.charts.get(chart.id)
    assert str(fetched.viz_type) == viz_type
    assert fetched.datasource_id == dataset.id
    assert fetched.params.to_dict() == chart.params.to_dict()

    fetched.slice_name = f"{chart.slice_name}-changed"
    fetched.save()
    assert client.charts.get(chart.id).slice_name.endswith("-changed")


def test_delete_returns_true_and_the_chart_is_gone(client, add_chart):
    chart = add_chart()

    assert client.charts.delete(chart.id) is True
    with pytest.raises(ResourceNotFoundError):
        client.charts.get(chart.id)


# --- Data ------------------------------------------------------------------------------------

@pytest.mark.parametrize("viz_type", ["table", "pie", "pivot_table_v2", "treemap_v2", "word_cloud", "funnel",
                                      "gauge_chart", "sunburst_v2"])
def test_chart_created_in_code_returns_data_from_its_query_context(client, add_chart, viz_type):
    chart = add_chart(viz_type)

    stored = client.get(client.join_urls(client.charts.base_url, chart.id)).json()["result"]["query_context"]
    assert json.loads(stored) == chart.ui_query_context()
    (result, *_) = client.charts.get_chart_data(chart.id)
    assert {value for row in result["data"] for value in row.values()} >= {"North", "South"}


def test_chart_built_in_code_gets_the_time_filter_a_dashboard_time_range_applies_to(client, add_chart):
    """Issue #22: as a new chart in the UI, a chart built in code gets a TEMPORAL_RANGE "No filter" on the dataset's
    temporal column; a time range given to it (as a dashboard time filter does) filters the data."""
    chart = add_chart("pie")
    stored = client.get(client.charts.object_url(chart.id)).json()["result"]

    time_filters = [f for f in json.loads(stored["params"])["adhoc_filters"] if f["operator"] == "TEMPORAL_RANGE"]
    assert [(f["subject"], f["comparator"]) for f in time_filters] == [("day", "No filter")]
    context = json.loads(stored["query_context"])
    for query_filter in context["queries"][0]["filters"]:
        if query_filter["op"] == "TEMPORAL_RANGE":
            query_filter["val"] = "2026-01-02 : 2026-01-03"
    (result, *_) = client.post(client.join_urls(client.charts.base_url, "data"), json=context).json()["result"]
    assert [row["campus"] for row in result["data"]] == ["South"]


def build_with_ui_defaults(viz_type: str, dataset) -> Chart:
    """A chart of each modeled viz_type, built in code on top of the UI defaults of a new chart."""
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=unique_name(viz_type), datasource=DataSource(id=dataset.id, type="table"))
    if viz_type == "histogram_v2":  # no metric: the bins count the rows of the column
        chart.set_column("total")
        return chart
    chart.add_simple_metric("count")
    if viz_type in ("table", "pie", "pivot_table_v2", "treemap_v2", "word_cloud", "funnel", "gauge_chart",
                    "sunburst_v2"):
        chart.add_simple_dimension("campus")
    elif viz_type in ("mixed_timeseries", "echarts_timeseries_line", "echarts_area", "heatmap_v2"):
        chart.set_x_axis("day")
        chart.add_simple_dimension("campus")
    elif viz_type in ("echarts_timeseries_bar", "big_number"):
        chart.set_x_axis("day" if viz_type == "big_number" else "campus")
    elif viz_type == "bubble_v2":
        chart.add_custom_metric("total_sum", sql_expression="SUM(total)")
        chart.add_custom_metric("total_max", sql_expression="MAX(total)")
        chart.add_simple_dimension("campus")
    elif viz_type == "box_plot":
        chart.add_distribute_across("campus")
    elif viz_type == "cal_heatmap":
        chart.params.granularity_sqla = chart.query_context.form_data.granularity_sqla = "day"
    return chart


@pytest.mark.parametrize("viz_type", ["big_number_total", "box_plot", "cal_heatmap", "echarts_timeseries_bar",
                                      "mixed_timeseries", "pie", "pivot_table_v2", "table", "treemap_v2",
                                      "word_cloud", "echarts_timeseries_line", "echarts_area", "big_number", "funnel",
                                      "gauge_chart", "bubble_v2", "histogram_v2", "heatmap_v2", "sunburst_v2"])
def test_every_modeled_viz_type_built_on_ui_defaults_returns_data(client, dataset, cleanup, viz_type):
    chart = build_with_ui_defaults(viz_type, dataset)
    cleanup.chart(client.charts.add(chart))

    results = client.charts.get_chart_data(chart.id)
    rows = [row for result in results for row in result["data"]]
    assert rows, f"{viz_type}: no rows"
    assert client.charts.get(chart.id).params.to_dict() == chart.params.to_dict()


# --- Export and import -----------------------------------------------------------------------

def test_chart_saved_without_query_context_has_no_data_endpoint_in_6_1(client, dataset, cleanup):
    """Why charts built in code send a query_context (derive_query_context): Superset 6.1.0 answers the chart
    data of a chart saved without one with an error. The dashboard still renders it (the frontend builds the
    query from the params), but reports, alerts and cache warm-up use this endpoint. Newer Superset versions
    rebuild the query on the server (superset.common.form_data_query_context): when this test fails after a
    version bump, query_context may become optional (docs/superset-version-bump.md)."""
    params = new_chart("table", dataset).to_json()["params"]
    created = client.post(client.charts.base_url, json={
        "slice_name": unique_name("no-query-context"), "viz_type": "table", "datasource_id": dataset.id,
        "datasource_type": "table", "params": params}).json()["id"]
    cleanup.chart(created)

    assert client.get(client.charts.object_url(created)).json()["result"]["query_context"] is None
    with pytest.raises(BadRequestError, match="Chart has no query context saved"):
        client.charts.get_chart_data(created)


def test_export_and_import_a_chart(client, add_chart, cleanup, tmp_path):
    chart = add_chart()
    archive = tmp_path / "chart.zip"

    client.charts.export([chart.id], archive)
    with zipfile.ZipFile(archive) as content:
        assert any(n.endswith(".yaml") and "/charts/" in n for n in content.namelist())
    client.charts.delete(chart.id)

    assert client.charts.import_file(archive, overwrite=True)
    imported = client.charts.find(name_filter("slice_name", chart.slice_name), columns=["id"])
    for item in imported:  # the import may assign a new id
        cleanup.chart(item.id)
    assert len(imported) == 1

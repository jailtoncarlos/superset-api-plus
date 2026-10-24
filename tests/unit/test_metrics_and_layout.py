"""Adding metrics to charts created in code and validating layout width."""
import dataclasses
import importlib
import json

import pytest

from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import OrderBy
from supersetapiplus.dashboards.layout.legacy.items import MarkdownItemPosition
from supersetapiplus.dashboards.layout.legacy.metadata_position import MetadataPosition
from supersetapiplus.exceptions import NodePositionValidationError

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud"]


def new_chart(viz_type: str) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")
    return chart_class.instance(slice_name="new", datasource=DataSource(id=1, type="table"))


def test_orderby_exposes_values_and_is_immutable():
    order = OrderBy(automate=False, sort_ascending=False)

    assert order.automate is False
    assert order.sort_ascending is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        order.sort_ascending = True


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_add_simple_metric_builds_orderby_for_every_type(viz_type):
    chart = new_chart(viz_type)

    chart.add_simple_metric("count")

    assert chart.query_context.queries[0].orderby[0][0] == "count"


def test_table_sorts_descending_on_every_call_without_changing_default_orderby():
    default = OrderBy()
    chart = new_chart("table")

    chart.add_simple_metric("count", default)
    chart.add_simple_metric("sum", default)

    assert chart.query_context.queries[0].orderby == [("count", False), ("sum", False)]
    assert default == OrderBy(automate=True, sort_ascending=True)


def test_pie_created_in_code_serializes_orderby_without_extra_nesting():
    chart = new_chart("pie")
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")

    data = chart.to_json()

    # Pie/buildQuery.ts: sort_by_metric orders by the metric, descending.
    assert json.loads(data["query_context"])["queries"][0]["orderby"] == [["count", False]]
    assert json.loads(data["params"])["sort_by_metric"] is True


def test_layout_validate_rejects_component_without_relocate_that_overflows_the_row():
    pos = MetadataPosition()
    tab = pos.add_tab("Tab")
    first = pos.add_markdown("a", parent=tab, width=6)
    second = pos.add_markdown("b", parent=tab, width=4)
    assert second.parent is first.parent

    # _validate adds the item width to the width of the node siblings (here, the first one: 6).
    with pytest.raises(NodePositionValidationError, match="Total 14"):
        second._validate(MarkdownItemPosition(code="c", width=8, relocate=False))

    second._validate(MarkdownItemPosition(code="d", width=8, relocate=True))

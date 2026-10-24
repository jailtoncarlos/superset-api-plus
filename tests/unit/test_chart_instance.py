"""Creating charts from scratch with Chart.instance()."""
import importlib

import pytest

from supersetapiplus.core.datasource import DataSource
from supersetapiplus.charts.charts import Chart

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud"]


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_instance_creates_chart_bound_to_datasource(viz_type):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")

    chart = chart_class.instance(slice_name="new", datasource=DataSource(id=7, type="table"))

    assert str(chart.viz_type) == viz_type
    assert chart.datasource_id == 7
    assert chart.params.datasource == "7__table"


def test_chart_get_class_resolves_from_viz_type():
    # Current contract: the type module must be imported first (an explicit registry would remove this requirement).
    importlib.import_module("supersetapiplus.charts.table")
    assert Chart.get_class("table", "supersetapiplus.charts.table").__name__ == "TableChart"

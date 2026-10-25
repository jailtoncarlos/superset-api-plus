"""Creating charts from scratch with Chart.instance()."""
import importlib

import pytest

from supersetapiplus.core.datasource import DataSource
from supersetapiplus.charts.charts import Chart

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud", "treemap_v2", "echarts_timeseries_line",
             "echarts_area", "big_number", "funnel", "gauge_chart", "bubble_v2", "histogram_v2", "heatmap_v2",
             "sunburst_v2"]


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


def test_registry_resolves_every_modeled_viz_type_without_importing_it_first():
    for viz_type in VIZ_TYPES:
        chart_class = Chart.for_viz_type(viz_type)
        assert str(chart_class.VIZ_TYPE) == viz_type and issubclass(chart_class, Chart)
        assert Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}") is chart_class


def test_unmodeled_viz_type_is_unsupported():
    from supersetapiplus.exceptions import UnsupportedTypeError

    with pytest.raises(UnsupportedTypeError):
        Chart.for_viz_type("sankey_v2")

"""Criação de gráficos do zero por Chart.instance()."""
import importlib

import pytest

from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud"]


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_instance_cria_grafico_ligado_ao_datasource(viz_type):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")

    chart = chart_class.instance(slice_name="novo", datasource=DataSource(id=7, type="table"))

    assert str(chart.viz_type) == viz_type
    assert chart.datasource_id == 7
    assert chart.params.datasource == "7__table"

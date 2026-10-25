"""Creating charts from scratch with constructors and Chart.instance()."""
import importlib
import json

import pytest

from supersetapiplus.core.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.types import DatasourceType

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud", "treemap_v2", "echarts_timeseries_line",
             "echarts_area", "big_number", "funnel", "gauge_chart", "bubble_v2", "histogram_v2", "heatmap_v2",
             "sunburst_v2"]


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_constructor_defaults_to_table_datasource(viz_type):
    chart = Chart.for_viz_type(viz_type)(slice_name="new", datasource_id=7)

    assert chart.datasource_type is DatasourceType.TABLE
    assert chart.params.datasource == "7__table"
    assert chart.query_context.form_data.datasource == "7__table"
    assert chart.to_dict()["datasource_type"] == "table"


def test_default_datasource_is_in_chart_creation_payload():
    chart = Chart.for_viz_type("table")(slice_name="new", datasource_id=7)
    chart.add_simple_metric("count")

    payload = chart.to_json(columns=list(Chart.POST_FIELDS))

    assert payload["datasource_id"] == 7
    assert payload["datasource_type"] == "table"
    assert json.loads(payload["params"])["datasource"] == "7__table"


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_read_chart_without_datasource_type_keeps_it_absent(viz_type):
    data = {"id": 12, "slice_name": "stored", "params": {},
            "query_context": None}
    chart = Chart.for_viz_type(viz_type).from_json(data)

    assert isinstance(chart.datasource_type, MissingField)
    payload = chart.to_dict()
    assert "datasource_type" not in payload
    assert payload["params"] == data["params"]


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

"""Adição de métricas em gráficos criados por código e validação de largura do layout."""
import dataclasses
import importlib
import json

import pytest

from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import OrderBy
from supersetapiplus.dashboards.itemposition import MarkdownItemPosition
from supersetapiplus.dashboards.metadataposition import Metadataposition
from supersetapiplus.exceptions import NodePositionValidationError

VIZ_TYPES = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
             "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud"]


def novo_grafico(viz_type: str) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")
    return chart_class.instance(slice_name="novo", datasource=DataSource(id=1, type="table"))


def test_orderby_expoe_os_valores_e_e_imutavel():
    order = OrderBy(automate=False, sort_ascending=False)

    assert order.automate is False
    assert order.sort_ascending is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        order.sort_ascending = True


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_add_simple_metric_gera_orderby_em_todos_os_tipos(viz_type):
    chart = novo_grafico(viz_type)

    chart.add_simple_metric("count")

    assert chart.query_context.queries[0].orderby[0][0] == "count"


def test_tabela_ordena_decrescente_em_toda_chamada_sem_alterar_o_orderby_padrao():
    padrao = OrderBy()
    chart = novo_grafico("table")

    chart.add_simple_metric("count", padrao)
    chart.add_simple_metric("sum", padrao)

    assert chart.query_context.queries[0].orderby == [("count", False), ("sum", False)]
    assert padrao == OrderBy(automate=True, sort_ascending=True)


def test_pie_criado_por_codigo_serializa_orderby_sem_nivel_extra():
    chart = novo_grafico("pie")
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")

    dados = chart.to_json()

    assert json.loads(dados["query_context"])["queries"][0]["orderby"] == [["count", True]]
    assert json.loads(dados["params"])["sort_by_metric"] is True


def test_validate_do_layout_barra_componente_sem_relocate_que_estoura_a_linha():
    pos = Metadataposition()
    aba = pos.add_tab("Aba")
    primeiro = pos.add_markdown("a", parent=aba, width=6)
    segundo = pos.add_markdown("b", parent=aba, width=4)
    assert segundo.parent is primeiro.parent

    # _validate soma a largura do item à dos irmãos do nó (aqui, o primeiro: 6).
    with pytest.raises(NodePositionValidationError, match="Total 14"):
        segundo._validate(MarkdownItemPosition(code="c", width=8, relocate=False))

    segundo._validate(MarkdownItemPosition(code="d", width=8, relocate=True))

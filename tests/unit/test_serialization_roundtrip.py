"""Round-trip (from_json -> to_json) de charts com payloads no formato exportado pelo Superset.

Os payloads são sintéticos, mas reproduzem situações encontradas em dashboards reais:
query_context nulo, chaves não modeladas pela biblioteca e divergências que o próprio
Superset mantém entre params e query_context.form_data.
"""
import importlib
import json

import pytest

from supersetapiplus.charts.charts import Chart
from supersetapiplus.exceptions import ValidationError

DATASOURCE = "1__table"

METRIC_COUNT_DISTINCT = {
    "aggregate": "COUNT_DISTINCT",
    "column": {"column_name": "respondente_id", "type": "INTEGER", "filterable": True, "groupby": True},
    "expressionType": "SIMPLE",
    "hasCustomLabel": True,
    "label": "Respondentes",
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
        "series": "palavra",
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


def test_preserva_chaves_nao_modeladas_em_params():
    chart = load_chart("word_cloud", word_cloud_params())

    params = dumped(chart, "params")

    for key in ("series", "metric", "rotation", "size_from", "size_to", "color_scheme"):
        assert params[key] == word_cloud_params()[key], key


def test_query_context_nulo_e_preservado_e_datasource_vem_de_params():
    chart = load_chart("word_cloud", word_cloud_params(), query_context=None)

    assert chart.query_context is None
    assert chart.datasource_id == 1
    assert dumped(chart, "query_context") is None


def test_slice_id_e_parametros_de_requisicao_divergentes_sao_tolerados():
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


def test_form_data_com_datasource_legado_none_e_tolerado():
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


def test_mixed_timeseries_sem_chaves_da_query_b_no_form_data_e_tolerado():
    params, query_context = mixed_timeseries_payload({})

    chart = load_chart("mixed_timeseries", params, query_context)

    assert dumped(chart, "params")["groupby_b"] == ["uo_nome"]
    assert "groupby_b" not in dumped(chart, "query_context")["form_data"]


def test_mixed_timeseries_com_query_b_divergente_continua_bloqueado():
    params, query_context = mixed_timeseries_payload({"row_limit_b": 500})

    chart = load_chart("mixed_timeseries", params, query_context)

    with pytest.raises(ValidationError):
        chart.to_json()


def test_divergencia_real_entre_params_e_form_data_continua_bloqueada():
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


def test_tabela_agregada_somente_com_dimensoes_e_valida():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": [{"expressionType": "SQL", "label": "Respostas", "sqlExpression": "(resposta_valor)"}],
              "metrics": [], "percent_metrics": []}

    chart = load_chart("table", params)

    assert dumped(chart, "params")["groupby"] == params["groupby"]


def test_tabela_raw_sem_metricas_e_valida():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "raw",
              "all_columns": ["uo_nome", "curso"], "metrics": []}

    chart = load_chart("table", params)

    assert dumped(chart, "params")["all_columns"] == ["uo_nome", "curso"]


def test_tabela_sem_metricas_nem_dimensoes_e_invalida():
    params = {"datasource": DATASOURCE, "viz_type": "table", "query_mode": "aggregate",
              "groupby": [], "metrics": [], "percent_metrics": []}

    chart = load_chart("table", params)

    with pytest.raises(ValidationError):
        chart.to_json()


def test_comparacao_entre_classes_distintas_nao_falha_nem_altera_objetos():
    chart = load_chart("word_cloud", word_cloud_params())
    extra_before = dict(chart.params.extra_fields)

    assert (chart.params != object()) is True
    assert chart.params == chart.params
    assert chart.params.extra_fields == extra_before


def test_query_context_nulo_e_gravado_como_null_e_nao_como_texto():
    chart = load_chart("word_cloud", word_cloud_params(), query_context=None)

    assert chart.to_json()["query_context"] is None


def test_query_context_gravado_como_texto_null_e_lido_como_nulo():
    importlib.import_module("supersetapiplus.charts.pie")
    chart_class = Chart.get_class("pie", "supersetapiplus.charts.pie")
    params = {"datasource": DATASOURCE, "viz_type": "pie", "groupby": ["campus"], "metric": "count"}

    chart = chart_class.from_json({"id": 3, "slice_name": "p", "viz_type": "pie",
                                   "params": json.dumps(params), "query_context": "null"})

    assert chart.query_context is None


def test_datasource_do_topo_da_resposta_prevalece_sobre_params():
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
def test_grafico_novo_criado_por_from_json_recebe_o_datasource(viz_type, params):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart_class = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")

    chart = chart_class.from_json({"id": None, "slice_name": "novo", "viz_type": viz_type, "params": json.dumps(params),
                                   "query_context": None, "datasource_id": 29, "datasource_type": "table"})

    assert chart.params.datasource == "29__table"
    assert chart.query_context is None
    assert json.loads(chart.to_json()["params"])["datasource"] == "29__table"

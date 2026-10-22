"""Gráficos da biblioteca × gráficos salvos pelo Superset 6.1.0 (referências em tests/fixtures).

As referências são gráficos dos exemplos públicos do Superset. Verifica que a biblioteca os lê e
regrava sem perda e que os enums e padrões batem com os valores oficiais.
"""
import enum
import importlib
import json
from pathlib import Path

import pytest

from supersetapiplus.charts import types as T
from supersetapiplus.charts.charts import Chart
from supersetapiplus.dashboards.metadata import GlobalChartconfigurationScope, Metadata

REFERENCIAS = Path(__file__).parent.parent / "fixtures" / "referencias_ui_6.1.0"
TIPOS = sorted(p.stem for p in REFERENCIAS.glob("*.json") if p.stem != "INDICE")

# superset/utils/core.py FilterOperator (6.1.0) e src/explore/constants.ts Operators (frontend).
FILTER_OPERATOR_OFICIAL = {"==", "!=", ">", "<", ">=", "<=", "LIKE", "NOT LIKE", "ILIKE", "NOT ILIKE", "IS NULL",
                           "IS NOT NULL", "IN", "NOT IN", "IS TRUE", "IS FALSE", "TEMPORAL_RANGE"}
OPERATORS_FRONTEND = {"EQUALS", "NOT_EQUALS", "LESS_THAN", "LESS_THAN_OR_EQUAL", "GREATER_THAN",
                      "GREATER_THAN_OR_EQUAL", "IN", "NOT_IN", "LIKE", "ILIKE", "IS_NOT_NULL", "IS_NULL",
                      "LATEST_PARTITION", "IS_TRUE", "IS_FALSE", "TEMPORAL_RANGE"}


def referencia(viz_type: str) -> dict:
    return json.loads((REFERENCIAS / f"{viz_type}.json").read_text())


def classe(viz_type: str):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    return Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")


def json_ou_nulo(valor):
    return json.loads(valor) if isinstance(valor, str) else valor


@pytest.mark.parametrize("viz_type", TIPOS)
def test_referencia_da_ui_e_lida_e_regravada_sem_perda(viz_type):
    original = referencia(viz_type)

    dados = classe(viz_type).from_json(dict(original)).to_json()

    assert json_ou_nulo(dados["params"]) == json_ou_nulo(original["params"])
    assert json_ou_nulo(dados["query_context"]) == json_ou_nulo(original["query_context"])


def test_nenhum_valor_de_enum_e_tupla():
    tuplas = [f"{c.__name__}.{m.name}" for c in vars(T).values()
              if isinstance(c, type) and issubclass(c, enum.Enum) for m in c if isinstance(m.value, tuple)]

    assert tuplas == []


def test_operadores_de_filtro_sao_os_oficiais_e_o_operator_id_e_o_do_frontend():
    valores = {m.value for m in T.FilterOperatorType}
    nomes = {m.name for m in T.FilterOperatorType}

    assert valores - {"LATEST PARTITION"} == FILTER_OPERATOR_OFICIAL
    assert nomes - {"NOT_LIKE", "NOT_ILIKE"} == OPERATORS_FRONTEND
    assert T.FilterOperatorType.NOT_EQUAL is T.FilterOperatorType.NOT_EQUALS


def test_pivot_novo_tem_os_padroes_da_ui_e_serializa():
    from supersetapiplus.charts.pivot_table_v2 import PivotTableV2Option

    opcao = PivotTableV2Option()
    dados = opcao.to_dict()

    assert str(opcao.viz_type) == "pivot_table_v2"
    assert str(opcao.aggregateFunction) == "Sum"
    assert opcao.combineMetric is False
    assert "currency_format" not in dados or dados["currency_format"] is None
    assert T.ChartType.PIVOT_TALBE_V2 is T.ChartType.PIVOT_TABLE_V2


def test_padroes_do_json_metadata_seguem_o_superset_6():
    metadata = Metadata()

    assert GlobalChartconfigurationScope().rootPath == ["ROOT_ID"]
    assert metadata.shared_label_colors == []
    assert metadata.timed_refresh_immune_slices == []

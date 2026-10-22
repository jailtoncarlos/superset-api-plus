"""Enums da biblioteca × enums e choices do código-fonte do Superset (recorte em tests/fixtures).

A especificação OpenAPI tipa esses campos só como `string`; os valores aceitos vêm do fonte. Para
outra versão, gere o recorte com bin/scripts/extrair_enums_superset.py e aponte OFICIAL para ele.
"""
import json
from pathlib import Path

import pytest

from supersetapiplus.charts import types as T

OFICIAL = json.loads((Path(__file__).parent.parent / "fixtures" / "superset_enums_6.1.0.json").read_text())


def valores(enum_cls) -> set[str]:
    return {m.value for m in enum_cls}


# (enum da lib, valores oficiais, extras da lib permitidos e justificados)
CASOS = [
    (T.FilterOperatorType, set(OFICIAL["backend"]["FilterOperator"].values()),
     {"LATEST PARTITION"}),  # operador só do frontend (Operators.LatestPartition)
    (T.TimeGrain, set(OFICIAL["backend"]["TimeGrain"].values()), set()),
    (T.ResultFormat, set(OFICIAL["backend"]["ChartDataResultFormat"].values()), set()),
    (T.ResultType, set(OFICIAL["backend"]["ChartDataResultType"].values()), set()),
    (T.PivotAggregateFunction, set(OFICIAL["choices"]["pivot_table_v2.aggregateFunction"]), set()),
]


@pytest.mark.parametrize("enum_cls,oficiais,extras", CASOS, ids=[c[0].__name__ for c in CASOS])
def test_valores_do_enum_sao_os_do_codigo_fonte(enum_cls, oficiais, extras):
    assert valores(enum_cls) - extras == oficiais


def test_nomes_dos_operadores_sao_o_operator_id_do_frontend():
    nomes = {m.name for m in T.FilterOperatorType}
    # NOT_LIKE/NOT_ILIKE existem no backend, mas não no enum Operators do frontend.
    assert nomes - {"NOT_LIKE", "NOT_ILIKE"} == set(OFICIAL["frontend"]["Operators"].values())
    assert T.FilterOperatorType.NOT_EQUAL is T.FilterOperatorType.NOT_EQUALS

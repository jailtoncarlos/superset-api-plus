"""Library enums vs. enums and choices from the Superset source code (excerpt in tests/fixtures).

The OpenAPI specification types these fields only as `string`; the accepted values come from the
source. For another version, generate the excerpt with bin/scripts/extract_superset_enums.py and
point OFFICIAL to it.
"""
import json
from pathlib import Path

import pytest

from supersetapiplus.charts import types as T
from supersetapiplus.dashboards import layout as L
from supersetapiplus.dashboards import native_filters as NF

OFFICIAL = json.loads((Path(__file__).parent.parent / "fixtures" / "superset_enums_6.1.0.json").read_text())


def values(enum_cls) -> set[str]:
    return {m.value for m in enum_cls}


# (library enum, official values, library extras that are allowed and justified)
CASES = [
    (T.FilterOperatorType, set(OFFICIAL["backend"]["FilterOperator"].values()),
     {"LATEST PARTITION"}),  # frontend-only operator (Operators.LatestPartition)
    (T.TimeGrain, set(OFFICIAL["backend"]["TimeGrain"].values()), set()),
    (T.ResultFormat, set(OFFICIAL["backend"]["ChartDataResultFormat"].values()), set()),
    (T.ResultType, set(OFFICIAL["backend"]["ChartDataResultType"].values()), set()),
    (T.PivotAggregateFunction, set(OFFICIAL["choices"]["pivot_table_v2.aggregateFunction"]), set()),
    (NF.FilterType, set(OFFICIAL["frontend"]["FilterPlugins"].values()), set()),
    (NF.NativeFilterType, set(OFFICIAL["frontend"]["NativeFilterType"].values()), set()),
    (L.Background, set(OFFICIAL["constants"]["dashboard.backgrounds"].values()), set()),
    (L.HeaderSize, set(OFFICIAL["constants"]["dashboard.headerSizes"].values()), set()),
    # NEW_COMPONENT_SOURCE is the editor's drag source, never stored in position_json.
    (L.ComponentType, set(OFFICIAL["constants"]["dashboard.componentTypes"].values()) - {"NEW_COMPONENT_SOURCE"},
     set()),
]


@pytest.mark.parametrize("enum_cls,official,extras", CASES, ids=[c[0].__name__ for c in CASES])
def test_enum_values_match_the_source_code(enum_cls, official, extras):
    assert values(enum_cls) - extras == official


def test_operator_names_are_the_frontend_operator_ids():
    names = {m.name for m in T.FilterOperatorType}
    # NOT_LIKE/NOT_ILIKE exist in the backend but not in the frontend Operators enum.
    assert names - {"NOT_LIKE", "NOT_ILIKE"} == set(OFFICIAL["frontend"]["Operators"].values())
    assert T.FilterOperatorType.NOT_EQUAL is T.FilterOperatorType.NOT_EQUALS

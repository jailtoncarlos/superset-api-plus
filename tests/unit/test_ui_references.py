"""Library charts vs. charts saved by Superset 6.1.0 (references in tests/fixtures).

The references are charts from Superset's public examples. Checks that the library reads and
rewrites them without loss and that enums and defaults match the official values.
"""
import enum
import importlib
import json
from pathlib import Path

import pytest

from supersetapiplus.charts import types as T
from supersetapiplus.charts.charts import Chart
from supersetapiplus.dashboards.metadata import GlobalChartconfigurationScope, Metadata

REFERENCES = Path(__file__).parent.parent / "fixtures" / "ui_references_6.1.0"
VIZ_TYPES = sorted(p.stem for p in REFERENCES.glob("*.json") if p.stem != "INDEX")


def reference(viz_type: str) -> dict:
    return json.loads((REFERENCES / f"{viz_type}.json").read_text())


def chart_class(viz_type: str):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    return Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}")


def json_or_none(value):
    return json.loads(value) if isinstance(value, str) else value


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_ui_reference_is_read_and_rewritten_without_loss(viz_type):
    original = reference(viz_type)

    data = chart_class(viz_type).from_json(dict(original)).to_json()

    assert json_or_none(data["params"]) == json_or_none(original["params"])
    assert json_or_none(data["query_context"]) == json_or_none(original["query_context"])


def test_no_enum_value_is_a_tuple():
    tuples = [f"{c.__name__}.{m.name}" for c in vars(T).values()
              if isinstance(c, type) and issubclass(c, enum.Enum) for m in c if isinstance(m.value, tuple)]

    assert tuples == []


def test_new_pivot_has_ui_defaults_and_serializes():
    from supersetapiplus.charts.pivot_table_v2 import PivotTableV2Option

    option = PivotTableV2Option()
    data = option.to_dict()

    assert str(option.viz_type) == "pivot_table_v2"
    assert str(option.aggregateFunction) == "Sum"
    assert option.combineMetric is False
    assert "currency_format" not in data or data["currency_format"] is None
    assert T.ChartType.PIVOT_TALBE_V2 is T.ChartType.PIVOT_TABLE_V2


def test_json_metadata_defaults_follow_superset_6():
    metadata = Metadata()

    assert GlobalChartconfigurationScope().rootPath == ["ROOT_ID"]
    assert metadata.shared_label_colors == []
    assert metadata.timed_refresh_immune_slices == []

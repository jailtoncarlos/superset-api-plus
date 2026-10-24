"""A chart created in code gets the params the Superset UI gives a new chart of the same viz_type.

Reference: tests/fixtures/ui_defaults_<version>/, the form_data Explore posts for a new chart (controlPanel
defaults included), captured by bin/scripts/extract_ui_defaults.py. Two checks per viz_type:

- every key the library writes has the UI value, or is declared in NOT_IN_UI with the reason;
- every UI default read by buildQuery (supersetapiplus/charts/build_query.py) is written with the UI value,
  so the query_context derived from a new chart is the one the UI would derive.

Keys set by the builder methods (metrics, dimensions, filters) and keys the UI derives from the dataset
(its main datetime column) are not defaults and are left out.
"""
import importlib
import inspect
import json
import re
from pathlib import Path

import pytest

from supersetapiplus.core.model import ObjectDecoder
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts import build_query
from supersetapiplus.charts.charts import Chart

DEFAULTS = Path(__file__).parent.parent / "fixtures" / "ui_defaults_6.1.0"
VIZ_TYPES = json.loads((DEFAULTS / "INDEX.json").read_text())["viz_types"]

# Set by the chart builder methods, or by Superset when the chart is saved (dashboards).
USER_KEYS = {"datasource", "viz_type", "metrics", "metric", "groupby", "groupbyRows", "groupbyColumns", "columns",
             "all_columns", "percent_metrics", "series", "x_axis", "dashboards", "metrics_b", "groupby_b"}
# Derived by the UI from the dataset (TEMPORAL_RANGE filter and time column on its main datetime column).
DATASET_KEYS = {"adhoc_filters", "adhoc_filters_b", "temporal_columns_lookup", "granularity_sqla"}

# Keys the library writes that the UI does not send for a new chart, with the reason.
NOT_IN_UI: dict[str, dict[str, str]] = {}


def ui_defaults(viz_type: str) -> dict:
    return json.loads((DEFAULTS / f"{viz_type}.json").read_text())


def new_chart_params(viz_type: str) -> dict:
    module = f"supersetapiplus.charts.{viz_type}"
    importlib.import_module(module)
    chart = Chart.get_class(viz_type, module).instance(slice_name="new", datasource=DataSource(id=1, type="table"))
    return json.loads(json.dumps(chart.params.to_dict(), cls=ObjectDecoder))


def build_query_keys() -> set[str]:
    """form_data keys read by the buildQuery port, with the `_b` variants of the mixed chart's second query."""
    keys = set(re.findall(r"""(?:form_data|fd)(?:\.get\(|\[)["'](\w+)["']""", inspect.getsource(build_query)))
    return keys | {f"{key}_b" for key in keys}


def compared(keys) -> set[str]:
    return set(keys) - USER_KEYS - DATASET_KEYS


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_new_chart_writes_only_ui_defaults(viz_type):
    ui, params = ui_defaults(viz_type), new_chart_params(viz_type)
    allowed = NOT_IN_UI.get(viz_type, {})

    differences = {key: (params[key], ui.get(key, "<absent>")) for key in sorted(compared(params))
                   if key not in allowed and params[key] != ui.get(key, "<absent>")}

    assert differences == {}, "library value, UI value"


@pytest.mark.parametrize("viz_type", VIZ_TYPES)
def test_new_chart_has_the_ui_defaults_read_by_build_query(viz_type):
    ui, params = ui_defaults(viz_type), new_chart_params(viz_type)

    missing = {key: ui[key] for key in sorted(compared(set(ui) & build_query_keys())) if key not in params}

    assert missing == {}, "UI defaults read by buildQuery that the library does not write"


def test_not_in_ui_entries_are_still_written_by_the_library():
    stale = {viz: sorted(set(keys) - set(new_chart_params(viz))) for viz, keys in NOT_IN_UI.items()}

    assert all(not keys for keys in stale.values()), stale

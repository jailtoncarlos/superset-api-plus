"""Library enums vs. enums, choices and constants of the Superset source code (excerpt in tests/fixtures).

The OpenAPI specification types these fields only as `string`; the accepted values come from the source.
Every enum of the package must be listed in SOURCES (official values) or in LIBRARY_ONLY (with the reason):
a new enum without a declared source fails `test_every_enum_has_a_declared_source`.

To support another Superset version, generate the excerpt with bin/scripts/extract_superset_enums.py and
point OFFICIAL to it; the divergences show up as failures here.
"""
import enum
import importlib
import json
import pkgutil
import re
import warnings
from pathlib import Path

import pytest

import supersetapiplus
from supersetapiplus import query_string as Q
from supersetapiplus.charts import types as T
from supersetapiplus.core import types as B
from supersetapiplus.dashboards import layout as L
from supersetapiplus.dashboards import metadata as M
from supersetapiplus.dashboards import native_filters as NF
from supersetapiplus.dashboards.layout.legacy import items as IP

OFFICIAL = json.loads((Path(__file__).parent.parent / "fixtures" / "superset_enums_6.1.0.json").read_text())
BACKEND, FRONTEND, CHOICES = OFFICIAL["backend"], OFFICIAL["frontend"], OFFICIAL["choices"]


def official(group: dict, name: str) -> set:
    return set(group[name].values())


# Exact match: library enum -> official values (extras, when any, are in EXTRAS with the reason).
SOURCES = {
    B.DatasourceKind: official(BACKEND, "DatasourceKind"),
    B.LimitingFactor: official(BACKEND, "LimitingFactor"),
    B.ConfigurationMethod: official(BACKEND, "ConfigurationMethod"),
    B.SupersetErrorType: official(BACKEND, "SupersetErrorType"),
    B.ErrorLevel: official(BACKEND, "ErrorLevel"),
    T.FilterOperatorType: official(BACKEND, "FilterOperator"),
    T.TimeGrain: official(BACKEND, "TimeGrain"),
    T.ResultFormat: official(BACKEND, "ChartDataResultFormat"),
    T.ResultType: official(BACKEND, "ChartDataResultType"),
    T.GenericDataType: official(BACKEND, "GenericDataType"),
    T.ComparisonType: official(FRONTEND, "ComparisonType"),
    T.ComparisonColorScheme: official(FRONTEND, "ColorSchemeEnum"),
    T.ContributionType: official(FRONTEND, "ContributionType"),
    T.QueryModeType: official(FRONTEND, "QueryMode"),
    T.SortSeriesType: official(FRONTEND, "SortSeriesType"),
    T.FilterExpressionType: official(FRONTEND, "ExpressionTypes"),
    T.FilterClausesType: official(FRONTEND, "Clauses"),
    T.LegendOrientationType: official(FRONTEND, "LegendOrientation"),
    T.LegendType: official(FRONTEND, "LegendType"),
    T.StackStyleType: official(FRONTEND, "StackControlsValue"),
    T.LabelType: official(FRONTEND, "EchartsPieLabelType"),
    T.TreemapLabelType: official(FRONTEND, "EchartsTreemapLabelType"),
    T.Orientation: official(FRONTEND, "OrientationType"),
    T.MetricsLayoutEnum: official(FRONTEND, "MetricsLayoutEnum"),
    T.MetricType: set(OFFICIAL["objects"]["AGGREGATES"].values()),
    T.TitlePositionType: set(OFFICIAL["options"]["TITLE_POSITION_OPTIONS"]),
    T.ColumnType: set(OFFICIAL["unions"]["Column.columnType"]),
    T.HorizontalAlignType: set(OFFICIAL["unions"]["ColumnConfig.horizontalAlign"]),
    T.CurrencyPositionType: set(OFFICIAL["value_options"]["CURRENCY_SYMBOL_POSITION_OPTIONS"]),
    T.PivotAggregateFunction: set(CHOICES["pivot_table_v2.aggregateFunction"]),
    T.OrderType: set(CHOICES["pivot_table_v2.rowOrder"]),
    T.LabelRotation: set(CHOICES["echarts.xAxisLabelRotation"]),
    T.PercentMetricCalculation: set(CHOICES["table.percent_metric_calculation"]),
    T.WhiskerOptions: set(CHOICES["box_plot.whiskerOptions"]),
    T.CalendarDomain: set(CHOICES["cal_heatmap.domain_granularity"]),
    T.CalendarSubdomain: set(CHOICES["cal_heatmap.subdomain_granularity"]),
    NF.FilterType: official(FRONTEND, "FilterPlugins"),
    M.FilterBarOrientation: official(FRONTEND, "FilterBarOrientation"),
    NF.NativeFilterType: official(FRONTEND, "NativeFilterType"),
    L.Background: set(OFFICIAL["constants"]["dashboard.backgrounds"].values()),
    L.HeaderSize: set(OFFICIAL["constants"]["dashboard.headerSizes"].values()),
    # NEW_COMPONENT_SOURCE is the editor's drag source, never stored in position_json.
    L.ComponentType: set(OFFICIAL["constants"]["dashboard.componentTypes"].values()) - {"NEW_COMPONENT_SOURCE"},
}

# Library values allowed beyond the official ones, with the reason.
EXTRAS = {
    # Frontend-only operator (Operators.LatestPartition): the frontend sends it, the backend enum lacks it.
    T.FilterOperatorType: {"LATEST PARTITION"},
}

# The library models part of the official set: each library value must be official.
PARTIAL = {
    # Only the viz_types the library models (the frontend VizType lists all plugins).
    T.ChartType: official(FRONTEND, "VizType"),
    # Component types of the legacy layout builder (dashboards/itemposition.py, replaced by layout.py).
    IP.ItemPositionType: set(OFFICIAL["constants"]["dashboard.componentTypes"].values()),
    # Flask-AppBuilder filters usable in `q`: eqf/inf filter by a server-side function and Superset exposes
    # neither (tests/integration/test_data.py checks the operators against the server's /_info).
    Q.QueryOperator: set(OFFICIAL["fab"]["filter_operators"]),
}

# Open sets: every official value must be available; the library may hold more, for the reason given.
OPEN = {
    # Suggested formats of free-form controls: the extra members are valid d3 formats / NumberFormats ids.
    T.NumberFormatType: set(OFFICIAL["number_formats"]),
    T.DateFormatType: set(OFFICIAL["options"]["D3_TIME_FORMAT_OPTIONS"]),
    # The UI offers the CURRENCIES setting (configurable) plus AUTO; the library lists all ISO 4217 codes.
    T.CurrencyCodeType: set(OFFICIAL["config"]["CURRENCIES"]) | {OFFICIAL["identifiers"]["AUTO_CURRENCY_SYMBOL"]},
    # Backend and frontend DatasourceType differ (view / sl_table): the library holds the union.
    B.DatasourceType: official(BACKEND, "DatasourceType") | official(FRONTEND, "DatasourceType"),
}

# Enums with no counterpart in Superset, with the reason.
LIBRARY_ONLY = {
    T.SqlMapType: "deprecated: a column type is free text (native database type); kept for old imports",
    IP.PositionType: "placement option of the legacy layout builder; never sent to Superset",
}


def values(enum_cls) -> set:
    return {m.value for m in enum_cls}


def package_enums() -> set:
    found = set()
    for info in pkgutil.walk_packages(supersetapiplus.__path__, "supersetapiplus."):
        if info.name.endswith("graphviz"):  # optional dependency (graphviz)
            continue
        module = _import_quietly(info.name)
        found |= {obj for obj in vars(module).values()
                  if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj.__module__ == info.name
                  and len(obj)}
    return found


def test_every_enum_has_a_declared_source():
    declared = set(SOURCES) | set(PARTIAL) | set(OPEN) | set(LIBRARY_ONLY)
    missing = sorted(f"{e.__module__}.{e.__name__}" for e in package_enums() - declared)

    assert missing == [], ("enums without a declared source: add them to SOURCES/PARTIAL/OPEN with the official values "
                           f"(bin/scripts/extract_superset_enums.py) or to LIBRARY_ONLY with the reason: {missing}")


@pytest.mark.parametrize("enum_cls", list(SOURCES), ids=[e.__name__ for e in SOURCES])
def test_enum_values_match_the_source_code(enum_cls):
    assert values(enum_cls) - EXTRAS.get(enum_cls, set()) == SOURCES[enum_cls]


@pytest.mark.parametrize("enum_cls", list(PARTIAL), ids=[e.__name__ for e in PARTIAL])
def test_partial_enum_holds_only_official_values(enum_cls):
    assert values(enum_cls) <= PARTIAL[enum_cls]


@pytest.mark.parametrize("enum_cls", list(OPEN), ids=[e.__name__ for e in OPEN])
def test_open_enum_offers_every_official_value(enum_cls):
    assert OPEN[enum_cls] <= values(enum_cls)


def test_operator_names_are_the_frontend_operator_ids():
    names = {m.name for m in T.FilterOperatorType}
    # NOT_LIKE/NOT_ILIKE exist in the backend but not in the frontend Operators enum.
    assert names - {"NOT_LIKE", "NOT_ILIKE"} == set(FRONTEND["Operators"].values())



def test_dashboard_grid_limits_are_the_editor_ones():
    grid = OFFICIAL["numbers"]["dashboard.grid"]

    assert (L.GRID_COLUMN_COUNT, L.GRID_MIN_COLUMN_COUNT, L.GRID_MIN_ROW_UNITS, L.GRID_MAX_ROW_UNITS,
            L.DEFAULT_CHART_WIDTH) == (grid["GRID_COLUMN_COUNT"], grid["GRID_MIN_COLUMN_COUNT"],
                                       grid["GRID_MIN_ROW_UNITS"], grid["GRID_MAX_ROW_UNITS"],
                                       grid["GRID_DEFAULT_CHART_WIDTH"])


def test_dataset_metric_and_column_keys_are_those_of_the_update_schemas():
    from supersetapiplus.resources.datasets import Dataset, Datasets

    assert set(Dataset.METRIC_FIELDS) == set(OFFICIAL["schemas"]["DatasetMetricsPutSchema"])
    assert set(Dataset.COLUMN_FIELDS) == set(OFFICIAL["schemas"]["DatasetColumnsPutSchema"])
    assert set(Datasets.DUPLICATE_FIELDS) == set(OFFICIAL["schemas"]["DatasetDuplicateSchema"])
    assert set(Datasets.GET_OR_CREATE_FIELDS) == set(OFFICIAL["schemas"]["GetOrCreateDatasetSchema"])


def test_every_key_of_the_excerpt_is_checked_somewhere():
    """A key of the excerpt that no test or module names is checked by nothing: either a conformance test
    lost it or the extraction keeps a symbol the library no longer uses (remove it from the script)."""
    root = Path(__file__).parents[2]
    sources = [*Path(__file__).parent.glob("*.py"), *(root / "supersetapiplus").rglob("*.py")]
    literals = {m for p in sources for m in re.findall(r"""["']([^"'\n]+)["']""", p.read_text(encoding="utf-8"))}
    sections = ("backend", "frontend", "choices", "constants", "objects", "numbers", "options", "unions",
                "value_options", "schemas", "config", "operator_groups")
    orphans = [f"{section}.{key}" for section in sections for key in OFFICIAL[section] if key not in literals]
    assert orphans == []


def test_removed_viz_types_are_the_ones_superset_migrated():
    from supersetapiplus.charts.types.viz import REMOVED_VIZ_TYPES

    assert REMOVED_VIZ_TYPES == OFFICIAL["migrated_viz_types"]


def test_filter_operator_groups_are_those_of_the_filter_control():
    from supersetapiplus.charts.filters import DISABLE_INPUT_OPERATORS, MULTI_OPERATORS

    ids = FRONTEND["Operators"]  # Operators member -> operatorId (= FilterOperatorType member name)
    for group, library in (("MULTI_OPERATORS", MULTI_OPERATORS), ("DISABLE_INPUT_OPERATORS", DISABLE_INPUT_OPERATORS)):
        assert {operator.name for operator in library} == {ids[name] for name in OFFICIAL["operator_groups"][group]}


def _import_quietly(name: str):
    """Modules of the package, including the compatibility modules of old paths (they warn on import)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module(name)

"""Extract from Superset's source code the enums and `choices` used by the enum conformance tests.

The OpenAPI specification types many fields only as `string`; the accepted values live in the
source (backend and frontend enums, and controlPanel `choices`). This script downloads the files
of the given version and generates the versioned subset in tests/fixtures.

Usage:
    python bin/scripts/extract_superset_enums.py 6.1.0 > tests/fixtures/superset_enums_6.1.0.json
"""
import ast
import functools
import json
import re
import sys
import urllib.request

RAW_ROOT = "https://raw.githubusercontent.com/apache/superset/{version}/{path}"
# Flask-AppBuilder, at the version pinned by Superset in requirements/base.txt.
FAB_ROOT = "https://raw.githubusercontent.com/dpgaspar/Flask-AppBuilder/v{version}/{path}"
FAB_FILTERS = "flask_appbuilder/models/sqla/filters.py"

# Backend Python enums: (file, class).
BACKEND = [
    ("superset/utils/core.py", "FilterOperator"),
    ("superset/common/chart_data.py", "ChartDataResultFormat"),
    ("superset/common/chart_data.py", "ChartDataResultType"),
    ("superset/constants.py", "TimeGrain"),
    ("superset/sqllab/limiting_factor.py", "LimitingFactor"),
    ("superset/utils/core.py", "DatasourceType"),
    ("superset/utils/core.py", "GenericDataType"),
    ("superset/connectors/sqla/models.py", "DatasourceKind"),
    ("superset/models/core.py", "ConfigurationMethod"),
    ("superset/errors.py", "SupersetErrorType"),
    ("superset/errors.py", "ErrorLevel"),
]

# Backend marshmallow schemas whose field names the library uses (nested items the OpenAPI excerpt does
# not detail): (file, class).
SCHEMAS = [
    ("superset/datasets/schemas.py", "DatasetMetricsPutSchema"),
    ("superset/datasets/schemas.py", "DatasetColumnsPutSchema"),
    ("superset/datasets/schemas.py", "DatasetDuplicateSchema"),
    ("superset/datasets/schemas.py", "GetOrCreateDatasetSchema"),
]

# Frontend TypeScript enums: (file, enum).
FRONTEND = [
    ("superset-frontend/src/explore/constants.ts", "Operators"),
    ("superset-frontend/src/constants.ts", "FilterPlugins"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/Dashboard.ts", "NativeFilterType"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/Datasource.ts", "DatasourceType"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/Query.ts", "ContributionType"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/QueryFormData.ts", "QueryMode"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/AdvancedAnalytics.ts", "ComparisonType"),
    ("superset-frontend/packages/superset-ui-chart-controls/src/types.ts", "SortSeriesType"),
    ("superset-frontend/packages/superset-ui-chart-controls/src/types.ts", "ColorSchemeEnum"),
    ("superset-frontend/src/explore/components/controls/FilterControl/types.ts", "ExpressionTypes"),
    ("superset-frontend/src/explore/components/controls/FilterControl/types.ts", "Clauses"),
    ("superset-frontend/plugins/plugin-chart-echarts/src/types.ts", "LegendOrientation"),
    ("superset-frontend/plugins/plugin-chart-echarts/src/types.ts", "LegendType"),
    ("superset-frontend/plugins/plugin-chart-echarts/src/constants.ts", "StackControlsValue"),
    ("superset-frontend/plugins/plugin-chart-echarts/src/Pie/types.ts", "EchartsPieLabelType"),
    ("superset-frontend/plugins/plugin-chart-echarts/src/Timeseries/types.ts", "OrientationType"),
    ("superset-frontend/plugins/plugin-chart-pivot-table/src/types.ts", "MetricsLayoutEnum"),
    ("superset-frontend/packages/superset-ui-core/src/chart/types/VizType.ts", "VizType"),
    ("superset-frontend/src/dashboard/types.ts", "FilterBarOrientation"),
]

# String literal unions of TypeScript properties (`name?: 'a' | 'b'`): (key, file, property).
UNIONS = [
    ("Column.columnType", "superset-frontend/packages/superset-ui-core/src/query/types/Column.ts", "columnType"),
    ("ColumnConfig.horizontalAlign", "superset-frontend/packages/superset-ui-chart-controls/src/types.ts",
     "horizontalAlign"),
]

# Option lists of objects (`export const NAME = [{ value: 'a', ... }, ...]`): (file, name).
VALUE_OPTIONS = [
    ("superset-frontend/src/explore/components/controls/CurrencyControl/CurrencyControl.tsx",
     "CURRENCY_SYMBOL_POSITION_OPTIONS"),
]

# Default values of superset/config.py: names of list settings.
CONFIG = "superset/config.py"
CONFIG_LISTS = ["CURRENCIES"]

# Frontend object constants (`export const NAME = { KEY: 'value', ... }`): (file, name).
OBJECTS = [
    ("superset-frontend/src/explore/constants.ts", "AGGREGATES"),
]

# Frontend option lists (`export const NAME: [string, string][] = [['value', label], ...]`): (file, name).
OPTIONS = [
    ("superset-frontend/packages/superset-ui-chart-controls/src/utils/D3Formatting.ts", "D3_TIME_FORMAT_OPTIONS"),
    ("superset-frontend/packages/superset-ui-chart-controls/src/sections/chartTitle.tsx", "TITLE_POSITION_OPTIONS"),
]
D3_FORMATTING = "superset-frontend/packages/superset-ui-chart-controls/src/utils/D3Formatting.ts"
# Identifiers used as option values, resolved from their definition: (identifier, file).
IDENTIFIERS = [
    ("SMART_DATE_ID", "superset-frontend/packages/superset-ui-core/src/time-format/formatters/smartDate.ts"),
    ("AUTO_CURRENCY_SYMBOL", "superset-frontend/packages/superset-ui-core/src/currency-format/CurrencyFormats.ts"),
]

# Frontend string constants grouped by name: (key, file, regex on the constant name).
CONSTANTS = [
    ("dashboard.componentTypes", "superset-frontend/src/dashboard/util/componentTypes.ts", r"_TYPE$"),
    ("dashboard.headerSizes", "superset-frontend/src/dashboard/util/constants.ts", r"_HEADER$"),
    ("dashboard.backgrounds", "superset-frontend/src/dashboard/util/constants.ts", r"^BACKGROUND_"),
]

# Frontend numeric constants grouped by name: (key, file, regex on the constant name).
NUMBERS = [
    ("dashboard.grid", "superset-frontend/src/dashboard/util/constants.ts", r"^GRID_"),
]

# controlPanel control `choices`: (key, file, control name).
CHOICES = [
    ("pivot_table_v2.aggregateFunction",
     "superset-frontend/plugins/plugin-chart-pivot-table/src/plugin/controlPanel.tsx", "aggregateFunction"),
    ("pivot_table_v2.rowOrder",
     "superset-frontend/plugins/plugin-chart-pivot-table/src/plugin/controlPanel.tsx", "rowOrder"),
    ("echarts.xAxisLabelRotation", "superset-frontend/plugins/plugin-chart-echarts/src/controls.tsx",
     "xAxisLabelRotation"),
    ("box_plot.whiskerOptions", "superset-frontend/plugins/plugin-chart-echarts/src/BoxPlot/controlPanel.ts",
     "whiskerOptions"),
    ("cal_heatmap.domain_granularity", "superset-frontend/plugins/legacy-plugin-chart-calendar/src/controlPanel.ts",
     "domain_granularity"),
    ("cal_heatmap.subdomain_granularity",
     "superset-frontend/plugins/legacy-plugin-chart-calendar/src/controlPanel.ts", "subdomain_granularity"),
]

# Controls whose config is a named constant (`const NAME: ControlConfig = { ..., choices: [...] }`).
CONST_CHOICES = [
    ("table.percent_metric_calculation", "superset-frontend/plugins/plugin-chart-table/src/controlPanel.tsx",
     "percentMetricCalculationControl"),
]


COMMIT_URL = "https://api.github.com/repos/{repository}/commits/{ref}"


def non_empty(extract):
    """An extraction that finds nothing fails: a symbol renamed or reformatted in a new Superset version must
    stop the regeneration, not produce an empty set that the conformance tests would compare against."""
    @functools.wraps(extract)
    def checked(source, *args):
        result = extract(source, *args)
        if not result:
            raise ValueError(f"{extract.__name__}: nothing found for {args[0] if args else 'the source'!r}")
        return result
    return checked


def commit_sha(repository: str, ref: str) -> str:
    """Commit of a tag, recorded in the fixture with the paths it was extracted from."""
    with urllib.request.urlopen(COMMIT_URL.format(repository=repository, ref=ref), timeout=60) as response:
        return str(json.load(response)["sha"])


def download(version: str, path: str, root: str = RAW_ROOT) -> str:
    with urllib.request.urlopen(root.format(version=version, path=path), timeout=60) as response:
        return response.read().decode("utf-8")


@non_empty
def python_enum(source: str, class_name: str) -> dict[str, str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                target.id: item.value.value
                for item in node.body if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant)
                for target in item.targets if isinstance(target, ast.Name)
            }
    raise ValueError(f"class {class_name} not found")


@non_empty
def schema_fields(source: str, class_name: str) -> list[str]:
    """Field names of a marshmallow Schema class (class attributes assigned to a field)."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [target.id for item in node.body if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                    for target in item.targets if isinstance(target, ast.Name)]
    raise ValueError(f"class {class_name} not found")


@non_empty
def typescript_enum(source: str, name: str) -> dict[str, str]:
    body = re.search(rf"export enum {name} \{{(.*?)\}}", source, re.S)
    if not body:
        raise ValueError(f"enum {name} not found")
    return dict(re.findall(r"(\w+)\s*=\s*'([^']*)'", body.group(1)))


@non_empty
def typescript_numbers(source: str, name_pattern: str) -> dict[str, int]:
    found = dict(re.findall(r"export const (\w+) = (\d+);", source))
    return {name: int(value) for name, value in found.items() if re.search(name_pattern, name)}


@non_empty
def typescript_constants(source: str, name_pattern: str) -> dict[str, str]:
    found = dict(re.findall(r"export const (\w+) = '([^']*)';", source))
    return {name: value for name, value in found.items() if re.search(name_pattern, name)}


@non_empty
def control_choices(source: str, control: str) -> list:
    block = re.search(rf"name:\s*'{control}'.*?choices:\s*\[(.*?)\n\s*\],", source, re.S)
    if not block:
        raise ValueError(f"choices of {control} not found")
    return [int(number) if number else text
            for text, number in re.findall(r"\[\s*(?:'([^']+)'|(\d+))\s*,", block.group(1))]


@non_empty
def const_choices(source: str, name: str) -> list[str]:
    block = re.search(rf"const {name}\b[^=]*= \{{.*?choices:\s*\[(.*?)\n\s*\],", source, re.S)
    if not block:
        raise ValueError(f"choices of {name} not found")
    return re.findall(r"\[\s*'([^']+)'\s*,", block.group(1))


@non_empty
def typescript_object(source: str, name: str) -> dict[str, str]:
    body = re.search(rf"export const {name} = \{{(.*?)\}};", source, re.S)
    if not body:
        raise ValueError(f"object {name} not found")
    return dict(re.findall(r"(\w+):\s*'([^']*)'", body.group(1)))


@non_empty
def option_values(source: str, name: str, identifiers: dict[str, str]) -> list[str]:
    body = re.search(rf"export const {name}\b[^=]*= \[(.*?)\n\];", source, re.S)
    if not body:
        raise ValueError(f"options {name} not found")
    return [text or identifiers[identifier]
            for text, identifier in re.findall(r"^\s*\[\s*(?:'([^']*)'|(\w+)),", body.group(1), re.M)]


@non_empty
def typescript_union(source: str, prop: str) -> list[str]:
    union = re.search(rf"\b{prop}\??:\s*((?:'[^']*'\s*\|?\s*)+);", source)
    if not union:
        raise ValueError(f"union of {prop} not found")
    return re.findall(r"'([^']*)'", union.group(1))


@non_empty
def value_options(source: str, name: str) -> list[str]:
    body = re.search(rf"export const {name}\b[^=]*= \[(.*?)\n\];", source, re.S)
    if not body:
        raise ValueError(f"options {name} not found")
    return re.findall(r"value:\s*'([^']*)'", body.group(1))


@non_empty
def config_list(source: str, name: str) -> list:
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"setting {name} not found")


def fab_version(requirements: str) -> str:
    match = re.search(r"^flask-appbuilder==([\w.]+)$", requirements, re.M)
    if not match:
        raise ValueError("flask-appbuilder pin not found in requirements/base.txt")
    return match.group(1)


def fab_operators(source: str) -> list[str]:
    """Rison filter operators (`arg_name`) of the Flask-AppBuilder SQLAlchemy filters."""
    operators = sorted(set(re.findall(r'arg_name = "([^"]+)"', source)))
    if not operators:
        raise ValueError("Flask-AppBuilder filter operators not found")
    return operators


def number_formats(source: str) -> list[str]:
    """Suggested number formats of D3_FORMAT_OPTIONS (the control is free-form: other d3 formats are valid)."""
    formatted = re.search(r"const d3Formatted[^=]*= \[(.*?)\]\.map", source, re.S)
    options = re.search(r"export const D3_FORMAT_OPTIONS\b[^=]*= \[(.*?)\n\];", source, re.S)
    if not (formatted and options):
        raise ValueError("D3 number formats not found")
    literal = re.findall(r"\[\s*'([^']*)'|^\s*'([^']*)',\s*$", options.group(1), re.M)
    return (["SMART_NUMBER"] + re.findall(r"'([^']*)'", formatted.group(1))
            + [first or second for first, second in literal])


# Legacy viz types removed from Superset and the type their charts were migrated to.
MIGRATE_VIZ = "superset/migrations/shared/migrate_viz/processors.py"


@non_empty
def migrated_viz_types(source: str) -> dict[str, str]:
    """`source_viz_type` -> `target_viz_type` of the MigrateViz processors (class-level constants)."""
    pairs = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        values = {target.id: item.value.value for item in node.body if isinstance(item, ast.Assign)
                  for target in item.targets if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant)}
        if "source_viz_type" in values and "target_viz_type" in values:
            pairs[values["source_viz_type"]] = values["target_viz_type"]
    return pairs


# Groups of adhoc filter operators of the filter control: (file, constant).
OPERATOR_GROUPS = [
    ("superset-frontend/src/explore/constants.ts", "MULTI_OPERATORS"),
    ("superset-frontend/src/explore/constants.ts", "DISABLE_INPUT_OPERATORS"),
]


@non_empty
def operator_group(source: str, name: str) -> list[str]:
    """Members of the `Operators` enum listed in `export const <name> = new Set([...])` or `= [...]`."""
    match = re.search(rf"export const {name}\s*=\s*(?:new Set\()?\[(.*?)\]", source, re.S)
    if not match:
        raise SystemExit(f"{name} not found")
    return re.findall(r"Operators\.(\w+)", match.group(1))


def main(version: str) -> None:
    cache: dict[str, str] = {}

    def source(path: str) -> str:
        if path not in cache:
            cache[path] = download(version, path)
        return cache[path]

    identifiers = {name: typescript_constants(source(file), rf"^{name}$")[name] for name, file in IDENTIFIERS}
    fab = fab_version(source("requirements/base.txt"))
    subset = {
        "superset_version": version,
        "backend": {cls: python_enum(source(file), cls) for file, cls in BACKEND},
        "schemas": {cls: schema_fields(source(file), cls) for file, cls in SCHEMAS},
        "frontend": {name: typescript_enum(source(file), name) for file, name in FRONTEND},
        "choices": {**{key: control_choices(source(file), control) for key, file, control in CHOICES},
                    **{key: const_choices(source(file), name) for key, file, name in CONST_CHOICES}},
        "constants": {key: typescript_constants(source(file), pattern) for key, file, pattern in CONSTANTS},
        "objects": {name: typescript_object(source(file), name) for file, name in OBJECTS},
        "numbers": {key: typescript_numbers(source(file), pattern) for key, file, pattern in NUMBERS},
        "options": {name: option_values(source(file), name, identifiers) for file, name in OPTIONS},
        "number_formats": number_formats(source(D3_FORMATTING)),
        "unions": {key: typescript_union(source(file), prop) for key, file, prop in UNIONS},
        "value_options": {name: value_options(source(file), name) for file, name in VALUE_OPTIONS},
        "identifiers": identifiers,
        "config": {name: config_list(source(CONFIG), name) for name in CONFIG_LISTS},
        "fab": {"version": fab, "filter_operators": fab_operators(download(fab, FAB_FILTERS, FAB_ROOT))},
        "migrated_viz_types": migrated_viz_types(source(MIGRATE_VIZ)),
        "operator_groups": {name: operator_group(source(file), name) for file, name in OPERATOR_GROUPS},
    }
    # Where the excerpt comes from: the commits of the tags and the files read.
    subset["provenance"] = {
        "superset": {"repository": "apache/superset", "tag": version, "sha": commit_sha("apache/superset", version),
                     "paths": sorted(cache)},
        "flask_appbuilder": {"repository": "dpgaspar/Flask-AppBuilder", "tag": f"v{fab}",
                             "sha": commit_sha("dpgaspar/Flask-AppBuilder", f"v{fab}"), "paths": [FAB_FILTERS]},
    }
    json.dump(subset, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])

"""Extract from Superset's source code the enums and `choices` used by the enum conformance tests.

The OpenAPI specification types many fields only as `string`; the accepted values live in the
source (backend and frontend enums, and controlPanel `choices`). This script downloads the files
of the given version and generates the versioned subset in tests/fixtures.

Usage:
    python bin/scripts/extract_superset_enums.py 6.1.0 > tests/fixtures/superset_enums_6.1.0.json
"""
import ast
import json
import re
import sys
import urllib.request

RAW_ROOT = "https://raw.githubusercontent.com/apache/superset/{version}/{path}"

# Backend Python enums: (file, class).
BACKEND = [
    ("superset/utils/core.py", "FilterOperator"),
    ("superset/common/chart_data.py", "ChartDataResultFormat"),
    ("superset/common/chart_data.py", "ChartDataResultType"),
    ("superset/constants.py", "TimeGrain"),
]

# Frontend TypeScript enums: (file, enum).
FRONTEND = [
    ("superset-frontend/src/explore/constants.ts", "Operators"),
    ("superset-frontend/src/constants.ts", "FilterPlugins"),
    ("superset-frontend/packages/superset-ui-core/src/query/types/Dashboard.ts", "NativeFilterType"),
]

# Frontend string constants grouped by name: (key, file, regex on the constant name).
CONSTANTS = [
    ("dashboard.componentTypes", "superset-frontend/src/dashboard/util/componentTypes.ts", r"_TYPE$"),
    ("dashboard.headerSizes", "superset-frontend/src/dashboard/util/constants.ts", r"_HEADER$"),
    ("dashboard.backgrounds", "superset-frontend/src/dashboard/util/constants.ts", r"^BACKGROUND_"),
]

# controlPanel control `choices`: (key, file, control name).
CHOICES = [
    ("pivot_table_v2.aggregateFunction",
     "superset-frontend/plugins/plugin-chart-pivot-table/src/plugin/controlPanel.tsx", "aggregateFunction"),
]


def download(version: str, path: str) -> str:
    with urllib.request.urlopen(RAW_ROOT.format(version=version, path=path), timeout=60) as response:
        return response.read().decode("utf-8")


def python_enum(source: str, class_name: str) -> dict[str, str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                target.id: item.value.value
                for item in node.body if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant)
                for target in item.targets if isinstance(target, ast.Name)
            }
    raise ValueError(f"class {class_name} not found")


def typescript_enum(source: str, name: str) -> dict[str, str]:
    body = re.search(rf"export enum {name} \{{(.*?)\}}", source, re.S)
    if not body:
        raise ValueError(f"enum {name} not found")
    return dict(re.findall(r"(\w+)\s*=\s*'([^']*)'", body.group(1)))


def typescript_constants(source: str, name_pattern: str) -> dict[str, str]:
    found = dict(re.findall(r"export const (\w+) = '([^']*)';", source))
    return {name: value for name, value in found.items() if re.search(name_pattern, name)}


def control_choices(source: str, control: str) -> list[str]:
    block = re.search(rf"name:\s*'{control}'.*?choices:\s*\[(.*?)\n\s*\],", source, re.S)
    if not block:
        raise ValueError(f"choices of {control} not found")
    return re.findall(r"\[\s*'([^']+)'\s*,", block.group(1))


def main(version: str) -> None:
    cache: dict[str, str] = {}

    def source(path: str) -> str:
        if path not in cache:
            cache[path] = download(version, path)
        return cache[path]

    subset = {
        "superset_version": version,
        "backend": {cls: python_enum(source(file), cls) for file, cls in BACKEND},
        "frontend": {name: typescript_enum(source(file), name) for file, name in FRONTEND},
        "choices": {key: control_choices(source(file), control) for key, file, control in CHOICES},
        "constants": {key: typescript_constants(source(file), pattern) for key, file, pattern in CONSTANTS},
    }
    json.dump(subset, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])

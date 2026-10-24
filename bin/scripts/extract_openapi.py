"""Extract from Superset's official OpenAPI specification the subset used by the conformance tests.

Usage (downloads the official specification of the version from the Superset repository):
    python bin/scripts/extract_openapi.py <version> > tests/fixtures/superset_openapi_<version>.json
or, with an already downloaded file:
    python bin/scripts/extract_openapi.py <version> /path/to/openapi.json > ...

Keeps every route (methods only) and the create/update schemas of the resources the
library writes, with properties, types and required fields.
"""
import json
import sys
import urllib.request

SPEC_URL = "https://raw.githubusercontent.com/apache/superset/{version}/docs/static/resources/openapi.json"

RESOURCES = ["ChartRestApi", "DashboardRestApi", "DatasetRestApi", "DatabaseRestApi", "SavedQueryRestApi",
             "CssTemplateRestApi"]


def schema_subset(schema: dict) -> dict:
    properties = {
        name: {k: v for k, v in prop.items() if k in ("type", "nullable", "enum", "maxLength")}
        for name, prop in schema.get("properties", {}).items()
    }
    return {"properties": properties, "required": sorted(schema.get("required", []))}


def load_spec(version: str, path: str | None) -> dict:
    if path:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    with urllib.request.urlopen(SPEC_URL.format(version=version), timeout=120) as response:
        return json.load(response)


def main(version: str, path: str | None = None) -> None:
    spec = load_spec(version, path)
    schemas = spec["components"]["schemas"]
    subset = {
        "superset_version": version,
        "paths": {route: sorted(m for m in ops if m in ("get", "post", "put", "delete"))
                  for route, ops in sorted(spec["paths"].items())},
        "schemas": {f"{r}.{op}": schema_subset(schemas[f"{r}.{op}"])
                    for r in RESOURCES for op in ("post", "put") if f"{r}.{op}" in schemas},
    }
    json.dump(subset, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])  # version [file]

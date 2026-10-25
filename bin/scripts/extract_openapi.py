"""Extract from Superset's official OpenAPI specification the subset used by the conformance tests.

Usage (downloads the official specification of the version from the Superset repository):
    python bin/scripts/extract_openapi.py <version> > tests/fixtures/superset_openapi_<version>.json
or, with an already downloaded file:
    python bin/scripts/extract_openapi.py <version> /path/to/openapi.json > ...

Keeps every route (methods only) and the create/update schemas of the resources the
library writes, with properties, types and required fields.
"""
import json
import os
import sys
import urllib.request

SPEC_PATH = "docs/static/resources/openapi.json"
SPEC_URL = "https://raw.githubusercontent.com/apache/superset/{version}/" + SPEC_PATH
COMMIT_URL = "https://api.github.com/repos/apache/superset/commits/{ref}"

RESOURCES = ["ChartRestApi", "DashboardRestApi", "DatasetRestApi", "DatabaseRestApi", "SavedQueryRestApi",
             "CssTemplateRestApi"]


def github_api(url: str) -> urllib.request.Request:
    """Request to the GitHub API, authenticated with GITHUB_TOKEN when set (higher rate limit on shared CI runners)."""
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def schema_subset(schema: dict) -> dict:
    properties = {
        name: {k: v for k, v in prop.items() if k in ("type", "nullable", "enum", "maxLength")}
        for name, prop in schema.get("properties", {}).items()
    }
    return {"properties": properties, "required": sorted(schema.get("required", []))}


def commit_sha(ref: str) -> str:
    with urllib.request.urlopen(github_api(COMMIT_URL.format(ref=ref)), timeout=60) as response:
        return str(json.load(response)["sha"])


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
    if not path:  # downloaded from the tag: record where the excerpt comes from
        subset["provenance"] = {"repository": "apache/superset", "tag": version, "sha": commit_sha(version),
                                "paths": [SPEC_PATH]}
    json.dump(subset, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])  # version [file]

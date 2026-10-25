"""Extract the layouts (`position`) of the example dashboards shipped with Superset.

The example dashboards (``superset/examples/*/dashboard.yaml``) are exports made with the Superset editor,
so their layouts are what the dashboard renderer accepts. The layout validation tests check that none of
them is reported as invalid. This script downloads the files of the given version and generates the
versioned subset in tests/fixtures.

Usage:
    python bin/scripts/extract_example_layouts.py 6.1.0 > tests/fixtures/example_layouts_6.1.0.json
"""
import json
import os
import re
import sys
import urllib.request

import yaml

TREE_URL = "https://api.github.com/repos/apache/superset/git/trees/{version}?recursive=1"
COMMIT_URL = "https://api.github.com/repos/apache/superset/commits/{ref}"
RAW_ROOT = "https://raw.githubusercontent.com/apache/superset/{version}/{path}"
DASHBOARD_FILE = re.compile(r"^superset/examples/([^/]+)/dashboard\.yaml$")


def github_api(url: str) -> urllib.request.Request:
    """Request to the GitHub API, authenticated with GITHUB_TOKEN when set (higher rate limit on shared CI runners)."""
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def download(url: str | urllib.request.Request) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https URLs)
        return str(response.read().decode("utf-8"))


def commit_sha(ref: str) -> str:
    return str(json.loads(download(github_api(COMMIT_URL.format(ref=ref))))["sha"])


def dashboard_files(version: str) -> dict[str, str]:
    """Example name → path of its dashboard.yaml."""
    tree = json.loads(download(github_api(TREE_URL.format(version=version))))
    if tree.get("truncated"):
        raise SystemExit("The GitHub tree listing is truncated; the list of examples would be incomplete.")
    files = {}
    for entry in tree["tree"]:
        match = DASHBOARD_FILE.match(entry["path"])
        if match:
            files[match.group(1)] = entry["path"]
    return files


def main(version: str) -> None:
    files = dashboard_files(version)
    layouts = {}
    for name, path in sorted(files.items()):
        dashboard = yaml.safe_load(download(RAW_ROOT.format(version=version, path=path)))
        layouts[name] = {"dashboard_title": dashboard.get("dashboard_title"), "position": dashboard["position"]}
    output = {"version": version, "source": "superset/examples/*/dashboard.yaml", "layouts": layouts,
              "provenance": {"repository": "apache/superset", "tag": version, "sha": commit_sha(version),
                             "paths": sorted(files.values())}}
    json.dump(output, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

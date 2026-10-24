"""Extract the layouts (`position`) of the example dashboards shipped with Superset.

The example dashboards (``superset/examples/*/dashboard.yaml``) are exports made with the Superset editor,
so their layouts are what the dashboard renderer accepts. The layout validation tests check that none of
them is reported as invalid. This script downloads the files of the given version and generates the
versioned subset in tests/fixtures.

Usage:
    python bin/scripts/extract_example_layouts.py 6.1.0 > tests/fixtures/example_layouts_6.1.0.json
"""
import json
import re
import sys
import urllib.request

import yaml

TREE_URL = "https://api.github.com/repos/apache/superset/git/trees/{version}?recursive=1"
RAW_ROOT = "https://raw.githubusercontent.com/apache/superset/{version}/{path}"
DASHBOARD_FILE = re.compile(r"^superset/examples/([^/]+)/dashboard\.yaml$")


def download(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https URLs)
        return str(response.read().decode("utf-8"))


def dashboard_files(version: str) -> dict[str, str]:
    """Example name → path of its dashboard.yaml."""
    tree = json.loads(download(TREE_URL.format(version=version)))
    if tree.get("truncated"):
        raise SystemExit("The GitHub tree listing is truncated; the list of examples would be incomplete.")
    files = {}
    for entry in tree["tree"]:
        match = DASHBOARD_FILE.match(entry["path"])
        if match:
            files[match.group(1)] = entry["path"]
    return files


def main(version: str) -> None:
    layouts = {}
    for name, path in sorted(dashboard_files(version).items()):
        dashboard = yaml.safe_load(download(RAW_ROOT.format(version=version, path=path)))
        layouts[name] = {"dashboard_title": dashboard.get("dashboard_title"), "position": dashboard["position"]}
    output = {"version": version, "source": "superset/examples/*/dashboard.yaml", "layouts": layouts}
    json.dump(output, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

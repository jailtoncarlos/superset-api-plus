"""Generate the references of charts saved by Superset (tests/fixtures/ui_references_<version>).

Deterministic for the same version: the examples come from the Superset package itself.

Reads, from an instance with the public examples loaded (e.g. the test stack with
SUPERSET_LOAD_EXAMPLES=1), one chart per viz_type, located by title and type (ids change
from instance to instance), and writes only the fields used by the modeling, without those
that depend on the instance or the moment (ids, URLs, thumbnails, "11 months ago").

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/extract_ui_references.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.client import SupersetClient  # noqa: E402
from supersetapiplus.query_string import QueryOperator, QueryStringFilter  # noqa: E402

# viz_type -> chart title in the "one chart per type" set of the Superset examples
# (`superset load_examples`). cal_heatmap does not exist in the examples.
CHARTS = {
    "big_number_total": "Big Number",
    "box_plot": "Box Plot",
    "echarts_timeseries_bar": "Bar",
    "mixed_timeseries": "Mixed",
    "pie": "Pie",
    "pivot_table_v2": "Pivot Table",
    "table": "Table",
    "word_cloud": "Word Cloud",
}

FIELDS = ("slice_name", "viz_type", "params", "query_context", "datasource_type", "datasource_name_text",
          "description", "cache_timeout")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main(version: str) -> None:
    client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"],
                            os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    target_dir = ROOT / "tests" / "fixtures" / f"ui_references_{version}"
    target_dir.mkdir(parents=True, exist_ok=True)

    index = {}
    for viz_type, title in CHARTS.items():
        query_filter = QueryStringFilter()
        query_filter.add("slice_name", QueryOperator.EQUAL, title)
        query_filter.add("viz_type", QueryOperator.EQUAL, viz_type)
        response = client.find(client.charts.base_url, query_filter, ["id"], page_size=2).json()
        if response["count"] != 1:
            print(f"{viz_type}: {response['count']} charts '{title}' - skipped", file=sys.stderr)
            continue
        chart_id = response["result"][0]["id"]
        result = client.get(client.join_urls(client.charts.base_url, chart_id)).json()["result"]
        write_json(target_dir / f"{viz_type}.json", {field: result.get(field) for field in FIELDS})
        index[viz_type] = {"slice_name": title, "dataset": result.get("datasource_name_text"),
                           "query_context": "present" if result.get("query_context") else "null"}

    write_json(target_dir / "INDEX.json", index)
    print(f"{len(index)} references in {target_dir}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])

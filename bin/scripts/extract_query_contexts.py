"""Capture the query_context the Superset frontend builds for each reference chart.

In the Superset UI the `query_context` is derived from the chart `params` by the plugin's
`buildQuery`. The example charts are stored with `query_context: null`, so the reference is taken
from the frontend itself: the script opens each chart of tests/fixtures/ui_references_<version>
in Explore with a headless browser and records the body of the `POST /api/v1/chart/data`
request. Instance-dependent values (datasource id) are removed, so the output is deterministic
for the same version and the same example charts.

Requires the test stack with the public examples (SUPERSET_LOAD_EXAMPLES=1) and Playwright
(`pip install playwright`; it uses the installed Chromium or `CHROME_PATH`).

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/extract_query_contexts.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.client import SupersetClient  # noqa: E402
from supersetapiplus.query_string import QueryOperator, QueryStringFilter  # noqa: E402

CHART_DATA = "/api/v1/chart/data"
TIMEOUT_MS = 60_000


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def chart_id(client: SupersetClient, viz_type: str, title: str) -> int | None:
    query_filter = QueryStringFilter()
    query_filter.add("slice_name", QueryOperator.EQUAL, title)
    query_filter.add("viz_type", QueryOperator.EQUAL, viz_type)
    response = client.find(client.charts.base_url, query_filter, ["id"], page_size=2).json()
    return response["result"][0]["id"] if response["count"] == 1 else None


def scrub(value):
    """Removes instance-dependent ids: dataset column ids and the Explore url_params (slice_id)."""
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()
                if key != "url_params" and not (key == "id" and "column_name" in value)}
    return value


# form_data keys that identify the instance or the Explore session, not the chart.
INSTANCE_FORM_DATA = ("datasource", "slice_id", "dashboards", "url_params", "dashboardId")


def normalize(query_context: dict) -> dict:
    """Keeps the form_data given to buildQuery and what it produces, without instance ids."""
    form_data = {k: v for k, v in query_context["form_data"].items() if k not in INSTANCE_FORM_DATA}
    return {
        "form_data": scrub(form_data),
        "datasource": {"type": query_context["datasource"]["type"]},
        "queries": scrub(query_context["queries"]),
        "result_format": query_context.get("result_format"),
        "result_type": query_context.get("result_type"),
    }


def is_chart_data_of(request, pk: int) -> bool:
    """Only the request of this chart: a late request of the previous page must not be taken."""
    if CHART_DATA not in request.url or request.method != "POST" or not request.post_data:
        return False
    return json.loads(request.post_data).get("form_data", {}).get("slice_id") == pk


def capture(page, url: str, pk: int) -> dict:
    with page.expect_request(lambda r: is_chart_data_of(r, pk), timeout=TIMEOUT_MS) as info:
        page.goto(url)
    return json.loads(info.value.post_data)


def main(version: str) -> None:
    url = os.environ["SUPERSET_URL"].rstrip("/")
    client = SupersetClient(url, os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    references = ROOT / "tests" / "fixtures" / f"ui_references_{version}"
    target_dir = ROOT / "tests" / "fixtures" / f"ui_query_contexts_{version}"
    target_dir.mkdir(parents=True, exist_ok=True)

    index = json.loads((references / "INDEX.json").read_text())
    captured = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None)
        # The browser reuses the library's login session (cookie), avoiding the React login form.
        context = browser.new_context()
        context.add_cookies([{"name": c.name, "value": c.value, "url": url} for c in client.session.cookies])
        page = context.new_page()
        for viz_type, entry in sorted(index.items()):
            pk = chart_id(client, viz_type, entry["slice_name"])
            if pk is None:
                print(f"{viz_type}: chart '{entry['slice_name']}' not found - skipped", file=sys.stderr)
                continue
            write_json(target_dir / f"{viz_type}.json", normalize(capture(page, f"{url}/explore/?slice_id={pk}", pk)))
            captured[viz_type] = entry["slice_name"]
        browser.close()

    write_json(target_dir / "INDEX.json", captured)
    print(f"{len(captured)} query contexts in {target_dir}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])

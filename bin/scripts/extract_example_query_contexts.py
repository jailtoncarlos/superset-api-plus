"""Capture the frontend queries of every modeled chart on the Superset example dashboards.

Unlike extract_query_contexts.py (one representative per viz_type), this captures each example chart,
identified by its stable export UUID. Requires the test stack with SUPERSET_LOAD_EXAMPLES=1, Playwright
and Chromium (CHROME_PATH selects the browser). It never calls the library's query builder or saves charts.

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... CHROME_PATH=... \\
        python bin/scripts/extract_example_query_contexts.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

from extract_query_contexts import capture
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.client import SupersetClient  # noqa: E402
from supersetapiplus.exceptions import UnsupportedTypeError  # noqa: E402
from tests.integration.test_examples.references import INSTANCE_FIELDS, params_fingerprint, portable  # noqa: E402


def read_only_chart_request(route) -> None:
    """Let Explore read charts and build queries without persisting its automatic query_context PUT."""
    request = route.request
    if request.method == "GET":
        route.continue_()
    elif request.method == "PUT":
        # Explore expects the normal save response before continuing to request the chart's data.
        pk = int(request.url.split("?")[0].rstrip("/").rsplit("/", 1)[1])
        route.fulfill(json={"id": pk, "result": request.post_data_json})
    else:
        # Observe POST /chart/data but never send it (it too can persist a context for slice_id).
        route.abort()


def example_charts(client: SupersetClient, version: str) -> dict[int, dict]:
    titles = {item["dashboard_title"] for item in json.loads(
        (ROOT / "tests" / "fixtures" / f"example_layouts_{version}.json").read_text())["layouts"].values()}
    charts = {}
    for dashboard in client.dashboards.find_all(columns=["id", "dashboard_title"]):
        if dashboard.dashboard_title not in titles:
            continue
        titles.remove(dashboard.dashboard_title)
        url = client.join_urls(client.dashboards.base_url, dashboard.id, "charts")
        for chart in client.get(url).json()["result"]:
            try:
                client.charts.get(chart["id"])  # Select modeled types only; no query building.
            except UnsupportedTypeError:
                continue
            charts[chart["id"]] = client.get(client.join_urls(client.charts.base_url, chart["id"])).json()["result"]
    if titles or not charts:
        raise SystemExit(f"Missing example dashboards or charts: {sorted(titles)}")
    return charts


def main(version: str) -> None:
    url = os.environ["SUPERSET_URL"].rstrip("/")
    client = SupersetClient(url, os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    charts = example_charts(client, version)
    captured = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None)
        context = browser.new_context()
        context.add_cookies([{"name": c.name, "value": c.value, "url": url} for c in client.session.cookies])
        context.route("**/api/v1/chart/**", read_only_chart_request)
        page = context.new_page()
        for pk, source in sorted(charts.items(), key=lambda item: item[1]["uuid"]):
            query = capture(page, f"{url}/explore/?slice_id={pk}", pk)
            if not query.get("queries"):
                raise SystemExit(f"No frontend queries for {source['slice_name']!r}")
            query = portable(query)
            query["datasource"].pop("id", None)
            query["form_data"] = {k: v for k, v in query["form_data"].items() if k not in INSTANCE_FIELDS}
            captured[source["uuid"]] = {"slice_name": source["slice_name"], "viz_type": source["viz_type"],
                                        "params_sha256": params_fingerprint(source), "query_context": query}
            print(f"Captured {len(captured)}/{len(charts)}: {source['slice_name']}", file=sys.stderr)
        browser.close()
    for pk, source in charts.items():
        current = client.get(client.join_urls(client.charts.base_url, pk)).json()["result"]
        if any(current.get(field) != source.get(field) for field in ("params", "query_context")):
            raise SystemExit(f"Explore changed the original chart {source['slice_name']!r}; no captures written")
    target = ROOT / "tests" / "fixtures" / f"example_query_contexts_{version}.json"
    target.write_text(json.dumps({"version": version, "source": "Explore POST /api/v1/chart/data",
                                  "charts": captured}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])

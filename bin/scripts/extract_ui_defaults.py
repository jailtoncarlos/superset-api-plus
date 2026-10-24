"""Capture the params the Superset frontend gives to a new chart of each supported viz_type.

A chart created in the UI starts from the controlPanel defaults of its plugin. When Explore opens a new
chart (`/explore/?viz_type=...&datasource_type=table&datasource_id=...`) it posts the complete form_data,
defaults included, to `/api/v1/explore/form_data` (ExploreViewContainer → updateHistory → postFormData).
The script records that form_data for each viz_type, without instance ids, so the library defaults can be
compared with the UI ones.

Requires the test stack with the public examples (SUPERSET_LOAD_EXAMPLES=1) and Playwright
(`pip install playwright`; it uses the installed Chromium or `CHROME_PATH`).

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/extract_ui_defaults.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.client import SupersetClient  # noqa: E402

DATASET = "cleaned_sales_data"
FORM_DATA = "/api/v1/explore/form_data"
VIZ_TYPES = ["big_number_total", "box_plot", "cal_heatmap", "echarts_timeseries_bar", "mixed_timeseries", "pie",
             "pivot_table_v2", "table", "word_cloud"]
# form_data keys that identify the instance or depend on the dataset, not on the plugin defaults.
INSTANCE_KEYS = ("datasource", "slice_id", "url_params", "dashboards")
TIMEOUT_MS = 60_000


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def is_form_data_post(request) -> bool:
    return FORM_DATA in request.url and request.method == "POST" and bool(request.post_data)


def capture(page, url: str) -> dict:
    with page.expect_request(is_form_data_post, timeout=TIMEOUT_MS) as info:
        page.goto(url)
    form_data = json.loads(json.loads(info.value.post_data)["form_data"])
    return {key: value for key, value in form_data.items() if key not in INSTANCE_KEYS}


def main(version: str) -> None:
    url = os.environ["SUPERSET_URL"].rstrip("/")
    client = SupersetClient(url, os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    dataset_id = client.datasets.get_datasource(DATASET).id
    target_dir = ROOT / "tests" / "fixtures" / f"ui_defaults_{version}"
    target_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None)
        # The browser reuses the library's login session (cookie), avoiding the React login form.
        context = browser.new_context()
        context.add_cookies([{"name": c.name, "value": c.value, "url": url} for c in client.session.cookies])
        page = context.new_page()
        for viz_type in VIZ_TYPES:
            explore = f"{url}/explore/?viz_type={viz_type}&datasource_type=table&datasource_id={dataset_id}"
            write_json(target_dir / f"{viz_type}.json", capture(page, explore))
        browser.close()

    write_json(target_dir / "INDEX.json", {"dataset": DATASET, "viz_types": VIZ_TYPES})
    print(f"{len(VIZ_TYPES)} default form_data in {target_dir}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])

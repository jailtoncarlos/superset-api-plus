"""Capture which form_data keys read by the buildQuery port are controls of each supported viz_type.

Explore builds the form_data of a chart from the controls of its control panel only
(``getFormDataFromControls`` over ``getAllControlsState``, superset-frontend/src/explore/controlUtils): a key
stored in the params that is not a control of the viz_type (e.g. a leftover ``granularity_sqla`` on a table)
never reaches buildQuery. The script saves a temporary chart of each viz_type whose params set every key the
port reads (PROBE, on an example dataset, the temporal column in the dimensions so that the time controls are
shown), opens it in Explore and records which of those keys the frontend sends: those are the controls. Keys
the frontend adds for the request (datasource, extra_form_data, force, result_format...) are not probed.

Requires the test stack with the public examples (SUPERSET_LOAD_EXAMPLES=1) and Playwright
(`pip install playwright`; it uses the installed Chromium or `CHROME_PATH`).

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/extract_ui_controls.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

from extract_query_contexts import TIMEOUT_MS, capture
from extract_ui_defaults import DATASET, VIZ_TYPES, is_form_data_post
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.client import SupersetClient  # noqa: E402

# Legacy plugins (useLegacyApi) do not call /api/v1/chart/data: their form_data is taken from the
# /api/v1/explore/form_data request Explore sends when it opens the chart.
LEGACY = {"cal_heatmap"}
# Every key the buildQuery port reads as a control, with a value valid on DATASET (cleaned_sales_data).
PROBE = {
    "adhoc_filters": [], "aggregation": "LAST_VALUE", "all_columns": ["deal_size"], "annotation_layers": [],
    "bins": 5, "column": "quantity_ordered", "columns": ["deal_size"], "comparison_type": "values",
    "contributionMode": "row", "cumulative": False, "entity": "deal_size", "forecastEnabled": False,
    "forecastInterval": 0.8, "forecastPeriods": 10, "forecastSeasonalityDaily": True,
    "forecastSeasonalityWeekly": True, "forecastSeasonalityYearly": True, "granularity": "order_date",
    "granularity_sqla": "order_date", "group_others_when_limit_reached": False, "groupby": ["order_date"],
    "groupbyColumns": ["product_line"], "groupbyRows": ["order_date"], "limit": 10, "metric": "count",
    "metric_2": "count", "metrics": ["count"], "min_periods": 0, "normalize": False, "normalize_across": "heatmap",
    "order_by_cols": [], "order_desc": True, "percent_metric_calculation": "row_limit", "percent_metrics": [],
    "query_mode": "aggregate", "resample_method": "asfreq", "resample_rule": "1D", "rolling_periods": 1,
    "rolling_type": "None", "row_limit": 100, "row_offset": 0, "secondary_metric": "count", "series": "deal_size",
    "series_columns": ["deal_size"], "series_limit": 10, "series_limit_metric": "count", "server_page_length": 10,
    "server_pagination": False, "show_empty_columns": True, "show_totals": False, "size": "count",
    "sort_by_metric": True, "sort_x_axis": "alpha_asc", "sort_y_axis": "alpha_asc", "start_date_offset": "",
    "time_compare": [], "time_grain_sqla": "P1D", "time_range": "No filter", "timeseries_limit_metric": "count",
    "truncate_metric": True, "whiskerOptions": "Tukey", "x": "count", "x_axis": "order_date", "x_axis_sort": "count",
    "x_axis_sort_asc": True, "y": "count",
}
# Controls shown only for some values of others (``visibility``: Explore leaves hidden controls out of the
# form_data) are probed again with each of these value sets; a key is a control if any probe sends it.
# The x axis sort is shown for a non-temporal x axis without dimensions (isSortable, customControls.tsx).
SHOWN_BY = ({"server_pagination": True, "query_mode": "raw", "columns": ["order_date"]},
            {"x_axis": "deal_size", "groupby": [], "columns": []})
SUFFIXED = {"mixed_timeseries": "_b"}  # the second query of the mixed chart reads the same keys with this suffix


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def probe_params(viz_type: str, datasource: str, probe: dict) -> dict:
    params = {"viz_type": viz_type, "datasource": datasource, **probe}
    suffix = SUFFIXED.get(viz_type)
    if suffix:
        params.update({f"{key}{suffix}": value for key, value in probe.items()})
    return params


def sent_form_data(page, url: str, viz_type: str, pk: int) -> dict:
    explore = f"{url}/explore/?slice_id={pk}"
    if viz_type in LEGACY:
        with page.expect_request(is_form_data_post, timeout=TIMEOUT_MS) as info:
            page.goto(explore)
        return json.loads(json.loads(info.value.post_data)["form_data"])
    return capture(page, explore, pk)["form_data"]


def main(version: str) -> None:
    url = os.environ["SUPERSET_URL"].rstrip("/")
    client = SupersetClient(url, os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    dataset_id = client.datasets.get_datasource(DATASET).id
    controls = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None)
        # The browser reuses the library's login session (cookie), avoiding the React login form.
        context = browser.new_context()
        context.add_cookies([{"name": c.name, "value": c.value, "url": url} for c in client.session.cookies])
        for viz_type in VIZ_TYPES:
            found: set[str] = set()
            for variant, probe in enumerate((PROBE, *({**PROBE, **values} for values in SHOWN_BY))):
                params = probe_params(viz_type, f"{dataset_id}__table", probe)
                pk = client.post(client.charts.base_url, json={
                    "slice_name": f"superset-api-plus-controls-{viz_type}", "viz_type": viz_type,
                    "datasource_id": dataset_id, "datasource_type": "table", "params": json.dumps(params)}).json()["id"]
                page = context.new_page()  # a fresh page per probe: a reused one kept controls of the previous chart
                try:
                    sent = sent_form_data(page, url, viz_type, pk)
                except PlaywrightTimeout:
                    if not variant:
                        raise
                    # A variant can empty a control the plugin requires: Explore then sends no query.
                    print(f"{viz_type}: variant {variant} sends no query (a required control is empty)", file=sys.stderr)
                    continue
                finally:
                    page.close()
                    client.charts.delete(pk)
                probed = set(params) - {"viz_type", "datasource"}
                found |= probed & set(sent)
            controls[viz_type] = sorted(found)
            print(f"{viz_type}: {len(controls[viz_type])} of {len(probed)} probed keys are controls", file=sys.stderr)
        browser.close()
    write_json(ROOT / "tests" / "fixtures" / f"ui_controls_{version}.json", {
        "version": version, "dataset": DATASET, "probed": sorted(PROBE), "shown_by": list(SHOWN_BY),
        "source": "Explore form_data of a saved chart whose params set every probed key", "controls": controls})


if __name__ == "__main__":
    main(sys.argv[1])

"""Calibrate the chart sizing measures (supersetapiplus.dashboards.layout.sizing.SizingProfile) in a browser.

The script builds a calibration dashboard on the public example dataset ``birth_names`` (tables, a pivot table,
horizontal bars, a markdown block and a native filter, so the vertical filter bar is shown), opens it in Chromium on
each viewport and measures what the sizing formulas need: the chart frame and title, the table header, rows, footer,
search box and pagination, the pivot table, the bar band and axes (read from the chart canvas) and the markdown
styles. The dashboard and its charts are removed at the end, also when the script fails.

Some values are choices, not measures (``POLICY``): the empty space tolerated below a chart, the bar thickness that
reads well, the characters per line of the bar labels (wrapped by the consumer) and the label column width the
consumer fixes in its tables. They are written with the profile so a recalibration keeps them visible.

Scrollbars are shown (Playwright hides them in headless mode by default): the table plugin reserves their width
below the table, which is part of the table footer.

Requires the test stack with the public examples (SUPERSET_LOAD_EXAMPLES=1) and Playwright
(``uv run --with playwright``; it uses the installed Chromium or ``CHROME_PATH``).

Usage:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/calibrate_sizing.py 6.1.0 [--viewports 1366,1920]

Output: tests/fixtures/sizing_profile_<version>.json (``provenance`` and ``profile``).
"""
from __future__ import annotations

import argparse
import datetime
import importlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from supersetapiplus.charts.charts import Chart  # noqa: E402
from supersetapiplus.client import SupersetClient  # noqa: E402
from supersetapiplus.core.datasource import DataSource  # noqa: E402
from supersetapiplus.dashboards.dashboards import Dashboard  # noqa: E402
from supersetapiplus.dashboards.layout.sizing import (  # noqa: E402
    GRID_MIN_ROW_UNITS,
    Layout,
    SizingProfile,
    TableContent,
    estimate_markdown,
    estimate_pivot_table,
    estimate_table,
)
from supersetapiplus.query_string import QueryOperator, QueryStringFilter  # noqa: E402

DATASET = "birth_names"
PREFIX = "zz-superset-api-plus-calibration"
TIMEOUT_MS = 120_000
# Long enough to show every chart at once (the dashboard may render only the charts in view).
VIEWPORT_HEIGHT = 4000
# A neutral English text: its average character width is the one used to wrap titles and labels.
SAMPLE_TEXT = ("The quick brown fox jumps over the lazy dog while five boxing wizards jump quickly and "
               "a sphinx of black quartz judges my vow")
LONG_TITLE = "A chart title long enough to wrap in two lines on the narrowest chart of the calibration dashboard"
TABLE_ROWS = 10
BARS = 10
MARKDOWN = """# Heading 1

## Heading 2

### Heading 3

#### Heading 4

##### Heading 5

###### Heading 6

A paragraph of text.

- first item
- second item

1. first
2. second

---

**bold text** and normal text
"""

# Choices of the profile, not measured (see the module docstring).
POLICY: dict[str, Any] = {
    # Empty space tolerated below a chart on the widest viewport: two lines of table text. The pivot table label
    # column cannot be fixed in Superset 6.1 and widens on large screens, so it gets more.
    "max_empty": 96,
    "max_empty_pivot_table": 280,
    # Bar thickness that reads well, in px of the bar itself; the band is the thickness divided by the share of the
    # band the bar takes (measured).
    "bar_thickness": 30,
    "min_bar_thickness": 26,
    "max_bar_thickness": 40,
    # Characters per line of a bar label (the consumer wraps the labels in its query) and the space between the
    # labels of two neighboring bars.
    "bar_label_chars": 85,
    "bar_label_padding": 8,
    # Width of the label column the consumer fixes in its tables (columnWidth), in px.
    "table_label_column_width": 560,
    # Characters lost per line to word wrapping in markdown text, and the margin added to markdown heights.
    "markdown_wrap_slack_chars": 4,
    "markdown_margin_units": 1,
}

MEASURE_JS = """(args) => {
  const rect = (e) => e ? e.getBoundingClientRect() : null;
  const px = (v) => parseFloat(v) || 0;
  const style = (e) => getComputedStyle(e);
  const canvas = document.createElement('canvas').getContext('2d');
  const textWidth = (font, text) => { canvas.font = font; return canvas.measureText(text).width; };
  const fontOf = (e) => { const s = style(e); return `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`; };
  const holders = {};
  document.querySelectorAll('.dashboard-component-chart-holder').forEach((h) => {
    const title = h.querySelector('.header-title');
    if (title) holders[title.textContent.trim()] = h;
  });
  const md = document.querySelector('.dashboard-markdown');
  const out = {viewport: innerWidth, charts: {}, missing: []};
  for (const [key, title] of Object.entries(args.titles)) {
    const h = holders[title];
    if (!h) { out.missing.push(title); continue; }
    const header = h.querySelector('.header-title').parentElement;
    const titleArea = h.querySelector('.header-title');
    const chart = h.querySelector('.dashboard-chart');
    const anchor = titleArea.querySelector('a') || titleArea;
    const c = {holder: rect(h).height, width: rect(h).width, header: rect(header).height,
               header_margin: px(style(header).marginBottom), chart: rect(chart).height,
               title_area: rect(titleArea).width, title_line: px(style(anchor).lineHeight),
               title_char: textWidth(fontOf(anchor), args.sample) / args.sample.length,
               warning: !!h.querySelector('.header-controls .anticon-warning')};
    const tableArea = h.querySelector('.superset-chart-table > div');
    if (tableArea) {
      const tables = h.querySelectorAll('.superset-chart-table table');
      const thead = h.querySelector('.superset-chart-table thead');
      const rows = [...h.querySelectorAll('.superset-chart-table tbody tr')];
      const td = h.querySelector('.superset-chart-table tbody td');
      const th = h.querySelector('.superset-chart-table thead th');
      const control = h.querySelector('.dt-controls');
      const pagination = h.querySelector('.dt-pagination');
      Object.assign(c, {table_area: rect(tableArea).height, thead: rect(thead).height,
        rows: rows.map((r) => rect(r).height), text_line: px(style(td).lineHeight),
        cell_padding: px(style(td).paddingLeft) + px(style(td).paddingRight),
        cell_char: textWidth(fontOf(td), args.sample) / args.sample.length, first_column: rect(th).width,
        search: control ? rect(control).height + px(style(control).marginBottom) + px(style(control).marginTop) : 0,
        pagination: pagination ? rect(pagination).height + px(style(pagination).marginTop) : 0,
        tables: tables.length});
    }
    const pivot = h.querySelector('.pvtTable');
    if (pivot) {
      // The scrolling container of the pivot table: the table fits when it is not taller than its client area.
      let scroll = pivot.parentElement;
      while (scroll !== h && style(scroll).overflowY !== 'auto') scroll = scroll.parentElement;
      const thead = pivot.querySelector('thead');
      const rows = [...pivot.querySelectorAll('tbody tr')];
      const label = pivot.querySelector('tbody th');
      Object.assign(c, {pivot_area: scroll.clientHeight, pivot_overflow: scroll.scrollHeight - rect(pivot).height,
        pivot_thead: rect(thead).height,
        pivot_rows: rows.map((r) => rect(r).height), pivot_text_line: px(style(label).lineHeight),
        pivot_label: rect(label).width, pivot_cell_padding: px(style(label).paddingLeft) + px(style(label).paddingRight),
        pivot_char: textWidth(fontOf(label), args.sample) / args.sample.length});
    }
    const bars = h.querySelector('canvas');
    if (bars && !tableArea && !pivot) {
      const width = bars.width, height = bars.height;
      const ratio = height / rect(bars).height;
      const data = bars.getContext('2d').getImageData(0, 0, width, height).data;
      // Bars are the saturated pixels on a vertical line through the plot (axis, labels and grid lines are grey).
      const runs = [];
      const x = Math.round(width * 0.2);
      let start = -1;
      for (let y = 0; y <= height; y++) {
        let colored = false;
        if (y < height) {
          const i = (y * width + x) * 4;
          const [r, g, b, a] = [data[i], data[i + 1], data[i + 2], data[i + 3]];
          colored = a > 200 && Math.max(r, g, b) - Math.min(r, g, b) > 40;
        }
        if (colored && start < 0) start = y;
        if (!colored && start >= 0) { runs.push([start / ratio, y / ratio]); start = -1; }
      }
      Object.assign(c, {canvas: rect(bars).height, bar_runs: runs});
    }
    out.charts[key] = c;
  }
  if (md) {
    const box = md.querySelector('h1').parentElement;
    const pad = style(box);
    const styles = {};
    for (const tag of ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']) {
      const e = md.querySelector(tag);
      if (!e) continue;
      const s = style(e);
      styles[tag] = {font: px(s.fontSize), line: px(s.lineHeight) || rect(e).height, margin_top: px(s.marginTop),
                     margin_bottom: px(s.marginBottom)};
    }
    const p = md.querySelector('p');
    const strong = md.querySelector('strong');
    const hr = md.querySelector('hr');
    const ul = md.querySelector('ul');
    out.markdown = {padding: px(pad.paddingTop), styles,
      char_width_em: textWidth(fontOf(p), args.sample) / args.sample.length / px(style(p).fontSize),
      bold_width: textWidth(fontOf(strong), args.sample) / textWidth(fontOf(p), args.sample),
      rule_height: rect(hr).height, rule_margin: Math.max(px(style(hr).marginTop), px(style(hr).marginBottom)),
      list_margin: Math.max(px(style(ul).marginTop), px(style(ul).marginBottom)), list_indent: px(style(ul).paddingLeft)};
  }
  const bar = document.querySelector('[data-test="dashboard-filters-panel"]');
  out.filter_bar = bar ? rect(bar).width : 0;
  out.font = style(document.body).fontFamily;
  out.fonts_loaded = [...document.fonts].filter((f) => f.status === 'loaded').map((f) => `${f.family} ${f.weight}`);
  return out;
}"""


# Whether the content of each sized component overflows (scrolls): table body, pivot table and markdown.
OVERFLOW_JS = """(titles) => {
  const scrolls = (e) => e.scrollHeight > e.clientHeight + 1;
  const out = {};
  document.querySelectorAll('.dashboard-component-chart-holder').forEach((h) => {
    const title = h.querySelector('.header-title');
    const key = title && Object.keys(titles).find((k) => titles[k] === title.textContent.trim());
    if (!key) return;
    const body = [...h.querySelectorAll('.superset-chart-table div')].find((e) => getComputedStyle(e).overflowY === 'auto');
    let pivot = h.querySelector('.pvtTable');
    while (pivot && pivot !== h && getComputedStyle(pivot).overflowY !== 'auto') pivot = pivot.parentElement;
    out[key] = body ? scrolls(body) : (pivot && pivot !== h ? scrolls(pivot) : null);
  });
  const md = document.querySelector('.dashboard-markdown h1');
  out.markdown = md ? scrolls(md.parentElement) : null;
  return out;
}"""


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def set_params(chart: Chart, **values: Any) -> None:
    """Sets the values on the params and on the query context form_data (kept in sync, as Explore does)."""
    for target in (chart.params, getattr(chart.query_context, "form_data", None)):
        if target is not None:
            for key, value in values.items():
                setattr(target, key, value)


def new_chart(viz_type: str, dataset_id: int, title: str, dimension: str | None = None, **params: Any) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=f"{PREFIX} {title}", datasource=DataSource(id=dataset_id, type="table"))
    chart.add_simple_metric("count")
    if dimension:
        chart.add_simple_dimension(dimension)
    set_params(chart, **params)
    return chart


def build_dashboard(client: SupersetClient, dataset_id: int) -> tuple[Dashboard, dict[str, Chart], dict[str, str]]:
    """The calibration dashboard: each chart with its width in grid columns; returns the titles by key."""
    charts: dict[str, tuple[Chart, int]] = {
        "frame": (new_chart("table", dataset_id, "frame", "gender"), 12),
        "long_title": (new_chart("table", dataset_id, LONG_TITLE, "gender"), 4),
        "table": (new_chart("table", dataset_id, "table", "name", row_limit=TABLE_ROWS), 12),
        "narrow_table": (new_chart("table", dataset_id, "narrow table", "name", row_limit=TABLE_ROWS), 6),
        "search": (new_chart("table", dataset_id, "search", "name", row_limit=TABLE_ROWS * 3, include_search=True,
                             server_pagination=True, server_page_length=TABLE_ROWS), 12),
        "pivot": (new_chart("pivot_table_v2", dataset_id, "pivot", "name", row_limit=TABLE_ROWS * 2), 12),
        "bars": (new_chart("echarts_timeseries_bar", dataset_id, "bars", row_limit=BARS), 12),
        "bars_without_legend": (new_chart("echarts_timeseries_bar", dataset_id, "bars without legend",
                                          row_limit=BARS, show_legend=False), 12),
    }
    set_params(charts["pivot"][0], groupbyColumns=["gender"])
    for key in ("bars", "bars_without_legend"):
        charts[key][0].set_x_axis("state")
        set_params(charts[key][0], orientation="horizontal")
    dashboard = Dashboard(dashboard_title=PREFIX)
    client.dashboards.add(dashboard)
    titles = {}
    for key, (chart, width) in charts.items():
        title = chart.slice_name
        row = dashboard.position.add_row()
        dashboard.add_chart(chart, title, parent=row, width=width, height=60)
        titles[key] = title
    dashboard.position.add_markdown(MARKDOWN, parent=dashboard.position.add_row(), width=12, height=80)
    dashboard.json_metadata.add_native_filter("Gender", dataset=dataset_id, column="gender")
    dashboard.save()
    return dashboard, {key: chart for key, (chart, _) in charts.items()}, titles


def open_dashboard(page: Page, url: str, dashboard_id: int, titles: dict[str, str]) -> dict[str, Any]:
    page.goto(f"{url}/superset/dashboard/{dashboard_id}/", timeout=TIMEOUT_MS)
    page.wait_for_selector(".dashboard-markdown", timeout=TIMEOUT_MS)
    page.wait_for_function("""(n) => document.querySelectorAll('.dashboard-component-chart-holder canvas, '
        + '.dashboard-component-chart-holder table').length >= n""", arg=len(titles), timeout=TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
    # The theme font (a web font) changes how titles and labels wrap: measure only once it is loaded.
    page.evaluate("document.fonts.ready.then(() => document.fonts.status)")
    page.wait_for_timeout(2000)  # chart animations
    measured = page.evaluate(MEASURE_JS, {"titles": titles, "sample": SAMPLE_TEXT})
    if measured["missing"]:
        raise RuntimeError(f"charts not found on the dashboard: {measured['missing']}")
    return measured


def estimates(profile: SizingProfile, by_viewport: dict[int, dict[str, Any]], titles: dict[str, str]) -> dict[str, int]:
    """The minimum height, in grid units, the profile gives each table, pivot table and the markdown block."""
    charts = by_viewport[min(by_viewport)]["charts"]
    rows = {key: len(chart["rows"]) for key, chart in charts.items() if "rows" in chart}
    widths = {"long_title": 4, "narrow_table": 6}
    units = {key: estimate_table(TableContent(rows=count, title=titles[key], search=key == "search",
                                              pagination=key == "search"),
                                 profile, Layout(columns=widths.get(key, 12))).min_units
             for key, count in rows.items()}
    units["pivot"] = estimate_pivot_table(TableContent(rows=len(charts["pivot"]["pivot_rows"]), title=titles["pivot"]),
                                          profile).min_units
    units["markdown"] = estimate_markdown(MARKDOWN, profile).min_units
    return units


def resize(client: SupersetClient, dashboard: Dashboard, charts: dict[str, Chart], units: dict[str, int],
           delta: int) -> None:
    """Sets each estimated component to its estimate plus `delta` units."""
    ids = {chart.id: key for key, chart in charts.items()}
    for component in dashboard.position.components_of_type("CHART"):
        key = ids.get(component.meta.get("chartId"))
        if key in units:
            component.meta["height"] = units[key] + delta
    for component in dashboard.position.components_of_type("MARKDOWN"):
        component.meta["height"] = units["markdown"] + delta
    dashboard.save()


def verify(client: SupersetClient, page: Page, url: str, dashboard: Dashboard, charts: dict[str, Chart],
           titles: dict[str, str], units: dict[str, int]) -> tuple[list[str], dict[str, bool]]:
    """Checks the profile on the narrowest viewport: the content must fit (not scroll) at its estimated minimum
    height. Returns the problems and, for each component, whether it still fits one grid unit (8 px) below, where the
    rounding of the measures may put it. Two units below is not checked: the table plugin resizes only when its size
    changes by more than the scrollbar width (TableChart.tsx), so a few px are decided by the render order."""
    problems, fits_below = [], {}
    for delta in (0, -1):
        resize(client, dashboard, charts, units, delta)
        open_dashboard(page, url, dashboard.id, titles)
        overflow = page.evaluate(OVERFLOW_JS, titles)
        for key, height in units.items():
            if overflow.get(key) is None:
                problems.append(f"{key}: not found on the dashboard at {height + delta} units")
            elif delta == 0 and overflow[key]:
                problems.append(f"{key}: scrolls at its estimated minimum of {height} units")
            elif delta == -1 and height + delta >= GRID_MIN_ROW_UNITS:
                fits_below[key] = not overflow[key]
    return problems, fits_below


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def bar_measures(chart: dict[str, Any]) -> tuple[float, float]:
    """(band, share of the band taken by the bar) from the bar runs read on the canvas."""
    runs = chart["bar_runs"]
    if len(runs) != BARS:
        raise RuntimeError(f"expected {BARS} bars on the canvas, found {len(runs)}")
    centers = [(start + end) / 2 for start, end in runs]
    band = (centers[-1] - centers[0]) / (BARS - 1)
    return band, mean([end - start for start, end in runs]) / band


def profile_from(version: str, by_viewport: dict[int, dict[str, Any]]) -> dict[str, Any]:
    narrowest = by_viewport[min(by_viewport)]
    charts = narrowest["charts"]
    frame, long_title, table = charts["frame"], charts["long_title"], charts["table"]
    title_line = round(frame["title_line"], 1)
    extra_lines = (long_title["header"] - frame["header"]) / title_line
    if extra_lines < 1 or abs(extra_lines - round(extra_lines)) > 0.1:
        raise RuntimeError(f"the long title header grows by {extra_lines:.2f} title lines, not a whole number >= 1")
    frame_total = frame["holder"] - frame["chart"]
    label_column = POLICY["table_label_column_width"] - table["cell_padding"]
    pivot = charts["pivot"]
    band, bar_share = bar_measures(charts["bars"])
    without_legend_band, _ = bar_measures(charts["bars_without_legend"])
    plot = charts["bars"]["chart"] - BARS * band
    markdown = narrowest["markdown"]
    # Every viewport must give the same heights: only the widths change.
    for viewport, measured in by_viewport.items():
        other = measured["charts"]
        if abs(other["table"]["thead"] - table["thead"]) > 1 or abs(other["frame"]["header"] - frame["header"]) > 1:
            raise RuntimeError(f"heights differ on {viewport} px: the profile assumes they do not")
    return {
        "superset_version": version,
        "theme": "default",
        "viewports": sorted(by_viewport),
        "grid": {
            "page_margin": round(narrowest["viewport"] - frame["width"] - narrowest["filter_bar"], 1),
            "vertical_filter_bar": round(narrowest["filter_bar"], 1),
        },
        # The header grows by one title line per wrapped line; the padding holds the rest of the one-line frame.
        "frame": {
            "padding": round(frame_total - title_line, 1),
            "min_header": title_line,
            "title_line": title_line,
            "title_char": round(frame["title_char"], 2),
            "title_controls": round(frame["width"] - frame["title_area"], 1),
        },
        "table": {
            "header": round(table["thead"], 1),
            "narrow_header": round(charts["narrow_table"]["thead"], 1),
            "row": round(mean(table["rows"]), 1),
            "text_line": round(table["text_line"], 1),
            # Below the rows: what the plugin keeps from the chart height (scrollbar), plus 1 px of rounding.
            "footer": math.ceil(table["chart"] - table["table_area"]) + 1,
            "search": round(charts["search"]["search"], 1),
            "pagination": round(charts["search"]["pagination"], 1),
            "label_chars": math.floor(label_column / table["cell_char"]),
            "unfixed_label_chars": math.floor((table["first_column"] - table["cell_padding"]) / table["cell_char"]),
            "min_label_lines": 1,
        },
        "pivot_table": {
            "header": round(pivot["pivot_thead"], 1),
            "row": round(mean(pivot["pivot_rows"]), 1),
            "text_line": round(pivot["pivot_text_line"], 1),
            "footer": math.ceil(pivot["chart"] - pivot["pivot_area"] + pivot["pivot_overflow"]) + 1,
            "label_chars": math.floor((pivot["pivot_label"] - pivot["pivot_cell_padding"]) / pivot["pivot_char"]),
        },
        "bars": {
            "band": round(POLICY["bar_thickness"] / bar_share, 1),
            "min_band": round(POLICY["min_bar_thickness"] / bar_share, 1),
            "max_band": round(POLICY["max_bar_thickness"] / bar_share, 1),
            "axes_and_legend": math.ceil(plot),
            "axes_without_legend": math.ceil(charts["bars_without_legend"]["chart"] - BARS * without_legend_band),
            "label_chars": POLICY["bar_label_chars"],
            "label_line": 12,
            "label_padding": POLICY["bar_label_padding"],
        },
        "markdown": {
            "padding": markdown["padding"],
            "char_width_em": round(markdown["char_width_em"], 3),
            "wrap_slack_chars": POLICY["markdown_wrap_slack_chars"],
            "styles": markdown["styles"],
            "rule_height": round(markdown["rule_height"], 1),
            "rule_margin": markdown["rule_margin"],
            "list_margin": markdown["list_margin"],
            "list_indent": markdown["list_indent"],
            "bold_width": round(markdown["bold_width"], 3),
            "bold_extra_line": 0,
        },
        "max_empty": POLICY["max_empty"],
        "max_empty_pivot_table": POLICY["max_empty_pivot_table"],
        "markdown_margin_units": POLICY["markdown_margin_units"],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("version", help="Superset version of the instance, e.g. 6.1.0")
    parser.add_argument("--viewports", default="1366,1920", help="screen widths in px (default: 1366,1920)")
    parser.add_argument("--raw", type=Path, help="also write the raw browser measures to this file")
    args = parser.parse_args(argv)
    viewports = sorted(int(width) for width in args.viewports.split(","))
    url = os.environ["SUPERSET_URL"].rstrip("/")
    client = SupersetClient(url, os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    if client.server_version != args.version:
        raise SystemExit(f"the instance runs Superset {client.server_version}, not {args.version}")
    dataset_filter = QueryStringFilter()
    dataset_filter.add("table_name", QueryOperator.EQUAL, DATASET)
    dataset = client.datasets.find_one(dataset_filter)

    dashboard, charts, titles = build_dashboard(client, dataset.id)
    try:
        by_viewport = {}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None,
                                                 ignore_default_args=["--hide-scrollbars"])
            pages = {}
            for viewport in viewports:
                context = browser.new_context(viewport={"width": viewport, "height": VIEWPORT_HEIGHT},
                                              device_scale_factor=1)
                context.add_cookies([{"name": c.name, "value": c.value, "url": url} for c in client.session.cookies])
                pages[viewport] = context.new_page()
                by_viewport[viewport] = open_dashboard(pages[viewport], url, dashboard.id, titles)
            if args.raw:
                write_json(args.raw, by_viewport)
            profile = profile_from(args.version, by_viewport)
            units = estimates(SizingProfile.model_validate(profile), by_viewport, titles)
            problems, fits_below = verify(client, pages[viewports[0]], url, dashboard, charts, titles, units)
            chromium = browser.version
            browser.close()
    finally:
        client.dashboards.delete(dashboard.id)
        for chart in charts.values():
            client.charts.delete(chart.id)
    if problems:
        raise SystemExit("the measured profile does not predict the heights:\n" + "\n".join(problems))

    target = ROOT / "tests" / "fixtures" / f"sizing_profile_{args.version}.json"
    write_json(target, {
        "provenance": {
            "superset_version": args.version, "chromium": chromium, "viewports": viewports, "theme": "default",
            "font": by_viewport[viewports[0]]["font"], "dataset": DATASET, "policy": POLICY,
            "script": "bin/scripts/calibrate_sizing.py",
            # Check of the profile on the calibration dashboard (narrowest viewport): the estimated minimum height
            # of each component, where it fits, and whether it still fits one grid unit below.
            "verification": {key: {"min_units": units[key], "fits_one_unit_below": fits_below.get(key)}
                             for key in units},
            "date": datetime.date.today().isoformat(),
        },
        "profile": profile,
    })
    print(f"profile written to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()

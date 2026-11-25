"""Browser check of a dashboard saved in Superset: what each component looks like on each viewport of the profile.

Available as ``client.dashboard_sizing.check_in_browser`` (optional extra ``browser``: Playwright with Chromium). It
opens the dashboard in Chromium with the client's session (``client.enable_session_mode()``), on each viewport of
the sizing profile, and reports for each chart and markdown component shown: whether its content scrolls, the empty
space below a table or pivot table, the thickness of horizontal bars and whether its title is clipped, against the
tolerances of the profile. It complements :meth:`DashboardSizing.check`, which estimates from the data without a
browser. It never writes. Components in tabs that are not open when the dashboard loads are not drawn by Superset
and are reported as not shown.
"""
from __future__ import annotations

import os
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

from supersetapiplus.charts.charts import Chart, Charts
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.dashboards.layout import DashboardLayout
from supersetapiplus.dashboards.layout.sizing import ChartShape, SizingProfile, calibrated_profile, chart_shape
from supersetapiplus.exceptions import UnsupportedTypeError

TIMEOUT_MS = 120_000
# Long enough to draw every chart at once (the dashboard may render only the charts in view).
VIEWPORT_HEIGHT = 4000

# Measures of each chart and markdown holder: chart id (None for markdown), title, whether some content scrolls,
# the empty px below a table or pivot table, the bar runs of a canvas (y ranges of the saturated pixels on a vertical
# line through the plot) and whether the title is clipped.
MEASURE_JS = """(horizontalBars) => {
  const rect = (e) => e.getBoundingClientRect();
  const out = [];
  // A chart holder, or the markdown block (which is not always inside a chart holder), in DOM order.
  const holders = new Set([...document.querySelectorAll('.dashboard-component-chart-holder, .dashboard-markdown')]
    .map((e) => e.closest('.dashboard-component-chart-holder') || e));
  holders.forEach((h) => {
    const slice = h.querySelector('[data-test-chart-id]');
    const markdown = h.matches('.dashboard-markdown') || h.querySelector('.dashboard-markdown');
    if (!slice && !markdown) return;
    const chartId = slice ? Number(slice.getAttribute('data-test-chart-id')) : null;
    const title = h.querySelector('.header-title');
    const scrolls = [...h.querySelectorAll('*')].some((e) => ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)
      && e.scrollHeight > e.clientHeight + 1);
    const clipped = !!title && (title.scrollWidth > title.clientWidth + 1
      || title.scrollHeight > title.clientHeight + 1);
    const item = {chartId, title: title ? title.textContent.trim() : null, scrolls, empty: null, bars: null, clipped};
    const content = [...h.querySelectorAll('.superset-chart-table table, .dt-pagination, .pvtTable')];
    const chart = h.querySelector('.dashboard-chart');
    if (content.length && chart && !scrolls) {
      item.empty = rect(chart).bottom - Math.max(...content.map((e) => rect(e).bottom));
    }
    const canvas = h.querySelector('canvas');
    if (canvas && horizontalBars.includes(chartId)) {
      const ratio = canvas.height / rect(canvas).height;
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      const x = Math.round(canvas.width * 0.2);
      const runs = [];
      let start = -1;
      for (let y = 0; y <= canvas.height; y++) {
        let colored = false;
        if (y < canvas.height) {
          const i = (y * canvas.width + x) * 4;
          colored = data[i + 3] > 200 && Math.max(data[i], data[i + 1], data[i + 2])
            - Math.min(data[i], data[i + 1], data[i + 2]) > 40;
        }
        if (colored && start < 0) start = y;
        if (!colored && start >= 0) { runs.push((y - start) / ratio); start = -1; }
      }
      item.bars = runs;
    }
    out.push(item);
  });
  return out;
}"""


class _Client(Protocol):
    """What the browser check needs from SupersetClient (a protocol: services must not import the client layer)."""
    host: str
    charts: Charts
    dashboards: Dashboards

    @property
    def session(self) -> requests.Session:
        ...


@dataclass(frozen=True)
class BrowserComponent:
    """A chart or markdown component as drawn on one viewport: ``shown`` False when Superset did not draw it (a tab
    that is not open); the measures; and the problems found against the profile's tolerances."""
    component_id: str
    title: str
    viewport: int
    shown: bool
    scrolls: bool | None = None
    empty_px: float | None = None
    bar_px: float | None = None
    clipped_title: bool | None = None
    problems: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class BrowserReport:
    """The components of a dashboard on each viewport, in layout order per viewport."""
    dashboard_id: int
    components: tuple[BrowserComponent, ...] = field(default=())

    @property
    def problems(self) -> list[BrowserComponent]:
        return [item for item in self.components if item.problems]

    def summary(self) -> str:
        """One line per component and viewport: its problems, ok, or not shown."""
        lines = []
        for item in self.components:
            state = "; ".join(item.problems) if item.problems else ("ok" if item.shown else "not shown")
            lines.append(f"{item.title} @ {item.viewport} px: {state}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _Placed:
    component_id: str
    title: str
    chart_id: int | None
    shape: ChartShape | None


def _placed(layout: DashboardLayout, shapes: dict[int, ChartShape | None]) -> list[_Placed]:
    """Chart and markdown components in tree order (as on the dashboard)."""
    found: list[_Placed] = []

    def visit(component_id: str) -> None:
        component = layout.components.get(component_id) or {}
        meta = component.get("meta") or {}
        if component.get("type") == "CHART":
            chart_id = meta.get("chartId") if isinstance(meta.get("chartId"), int) else None
            title = str(meta.get("sliceNameOverride") or meta.get("sliceName") or component_id)
            found.append(_Placed(component_id, title, chart_id, shapes.get(chart_id) if chart_id else None))
        elif component.get("type") == "MARKDOWN":
            found.append(_Placed(component_id, f"markdown {component_id}", None, ChartShape.MARKDOWN))
        for child in component.get("children") or []:
            visit(child)

    visit("ROOT_ID")
    return found


def _empty_tolerance(shape: ChartShape | None, profile: SizingProfile) -> float | None:
    """Empty px tolerated below a table (the tolerated space plus the footer the plugin keeps below the rows)."""
    if shape is ChartShape.TABLE:
        return profile.max_empty + profile.table.footer
    if shape is ChartShape.PIVOT_TABLE:
        return profile.max_empty_pivot_table + profile.pivot_table.footer
    return None


def _problems(placed: _Placed, measured: dict[str, Any], profile: SizingProfile, scrolls_by_design: bool,
              bar_px: float | None) -> tuple[str, ...]:
    """The problems of a drawn component against the profile's tolerances."""
    found = []
    if measured["scrolls"] and not scrolls_by_design:
        found.append("the content scrolls")
    tolerance = _empty_tolerance(placed.shape, profile)
    if tolerance is not None and measured["empty"] is not None and measured["empty"] > tolerance:
        found.append(f"{measured['empty']:.0f} px empty below the content (tolerated {tolerance:.0f})")
    share = profile.bars.bar_share
    if bar_px is not None and share is not None:
        low, high = profile.bars.min_band * share, profile.bars.max_band * share
        if not low - 1 <= bar_px <= high + 1:
            found.append(f"bars {bar_px:.0f} px thick, outside {low:.0f}-{high:.0f} px")
    if measured["clipped"]:
        found.append("the title is clipped")
    return tuple(found)


def _bar_px(runs: list[float] | None) -> float | None:
    return sum(runs) / len(runs) if runs else None


def _match(placed: list[_Placed], drawn: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The measures of each placed component: charts by chart id (in order when a chart is placed twice), markdown in
    order when every markdown component is drawn (with tabs, Superset draws only the open ones)."""
    by_chart: dict[int, list[dict[str, Any]]] = {}
    for measures in drawn:
        if measures["chartId"] is not None:
            by_chart.setdefault(measures["chartId"], []).append(measures)
    markdown = [measures for measures in drawn if measures["chartId"] is None]
    placed_markdown = [component for component in placed if component.shape is ChartShape.MARKDOWN]
    matched: dict[str, dict[str, Any]] = {}
    if len(markdown) == len(placed_markdown):
        matched.update({component.component_id: measures
                        for component, measures in zip(placed_markdown, markdown, strict=True)})
    for component in placed:
        if component.chart_id is not None and by_chart.get(component.chart_id):
            matched[component.component_id] = by_chart[component.chart_id].pop(0)
    return matched


class DashboardBrowserCheck:
    """Browser check of saved dashboards (see the module docstring); it never writes."""

    def __init__(self, client: _Client) -> None:
        self.client = client

    def check(self, dashboard_id: int, profile: SizingProfile | None = None, scrolls: Collection[int | str] = (),
              chrome_path: str | None = None) -> BrowserReport:
        """Opens the dashboard on each viewport of the profile and measures each component.

        Args:
            dashboard_id: the dashboard.
            profile: the viewports and tolerances (default: the calibrated profile of the target Superset version).
            scrolls: components that scroll by design, by chart id or component id (their scrolling is not reported).
            chrome_path: the Chromium executable (default: ``CHROME_PATH``, else the one installed by Playwright).
        """
        if not self.client.session.cookies.get_dict():
            raise ValueError("the browser check opens the dashboard with the client's session cookie: call "
                             "client.enable_session_mode() first")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise ImportError("the browser check needs Playwright: pip install 'superset-api-plus[browser]', then "
                              "playwright install chromium") from error
        profile = profile or calibrated_profile()
        layout: DashboardLayout = self.client.dashboards.get(dashboard_id).position_json
        placed = _placed(layout, self._shapes(layout))
        if not placed:  # nothing to measure: the dashboard draws no chart or markdown block
            return BrowserReport(dashboard_id)
        bars = [item.chart_id for item in placed if item.shape is ChartShape.HORIZONTAL_BARS]
        url = self.client.host.rstrip("/")
        # Read after the API reads above, which renew the session when it expired.
        cookies = self.client.session.cookies.get_dict()
        items: list[BrowserComponent] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome_path or os.getenv("CHROME_PATH") or None,
                                                 ignore_default_args=["--hide-scrollbars"])
            try:
                for viewport in profile.viewports:
                    context = browser.new_context(viewport={"width": viewport, "height": VIEWPORT_HEIGHT},
                                                  device_scale_factor=1)
                    context.add_cookies([{"name": name, "value": value, "url": url}
                                         for name, value in cookies.items()])
                    page = context.new_page()
                    page.goto(f"{url}/superset/dashboard/{dashboard_id}/", timeout=TIMEOUT_MS)
                    page.wait_for_selector(".dashboard-component-chart-holder, .dashboard-markdown",
                                           timeout=TIMEOUT_MS)
                    page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
                    page.evaluate("document.fonts.ready.then(() => document.fonts.status)")
                    page.wait_for_timeout(2000)  # chart animations
                    drawn = page.evaluate(MEASURE_JS, bars)
                    items += self._components(placed, drawn, viewport, profile, scrolls)
                    context.close()
            finally:
                browser.close()
        return BrowserReport(dashboard_id, tuple(items))

    def _shapes(self, layout: DashboardLayout) -> dict[int, ChartShape | None]:
        """The sizing shape of each chart of the layout (None when not covered or not readable)."""
        shapes: dict[int, ChartShape | None] = {}
        for component in layout.components.values():
            chart_id = (component.get("meta") or {}).get("chartId") if isinstance(component, dict) else None
            if not isinstance(chart_id, int) or chart_id in shapes:
                continue
            try:
                chart = self.client.charts.get(chart_id)
            except UnsupportedTypeError:
                chart = None
            shapes[chart_id] = chart_shape(chart.explore_params()) if isinstance(chart, Chart) else None
        return shapes

    @staticmethod
    def _components(placed: list[_Placed], drawn: list[dict[str, Any]], viewport: int, profile: SizingProfile,
                    scrolls: Collection[int | str]) -> list[BrowserComponent]:
        matched = _match(placed, drawn)
        found = []
        for item in placed:
            measured = matched.get(item.component_id)
            if measured is None:
                found.append(BrowserComponent(item.component_id, item.title, viewport, shown=False))
                continue
            by_design = item.component_id in scrolls or item.chart_id in scrolls
            bar_px = _bar_px(measured["bars"])
            found.append(BrowserComponent(
                item.component_id, measured["title"] or item.title, viewport, shown=True,
                scrolls=measured["scrolls"], empty_px=measured["empty"], bar_px=bar_px,
                clipped_title=measured["clipped"],
                problems=_problems(item, measured, profile, by_design, bar_px)))
        return found

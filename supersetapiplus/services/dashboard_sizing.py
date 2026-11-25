"""Sizing check of a dashboard saved in Superset: does each component's height fit its content?

Available as ``client.dashboard_sizing``. It reads the dashboard layout and, for each table, pivot table and
horizontal bars chart, the data the chart shows (rows, labels and bars, through ``POST /api/v1/chart/data`` with the
query the Superset UI builds from the chart's params), estimates the height its content needs
(:mod:`supersetapiplus.dashboards.layout.sizing`) and compares it with the stored height. Markdown blocks are
estimated from their text. It never writes: the result is a :class:`SizingReport` and a
:class:`~supersetapiplus.exceptions.SizingWarning` per component that does not fit.
"""
from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

import requests

from supersetapiplus.charts.charts import Chart, Charts
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.dashboards.layout import DashboardLayout
from supersetapiplus.dashboards.layout.sizing import (
    BarsContent,
    ChartShape,
    Content,
    Layout,
    SizingEstimate,
    SizingProfile,
    TableContent,
    calibrated_profile,
    chart_shape,
    estimate,
)
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.exceptions import BadRequestError, SizingWarning, UnsupportedTypeError


class _Client(Protocol):
    """What the service needs from SupersetClient (a protocol: services must not import the client layer)."""
    charts: Charts
    dashboards: Dashboards

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        ...

    @staticmethod
    def join_urls(*args: object) -> str:
        ...


@dataclass(frozen=True)
class ComponentSizing:
    """The check of one chart or markdown component: its shape (None for charts the formulas do not cover), the
    estimate and the problem when its height does not fit, or why it was not checked (``skipped``)."""
    component_id: str
    title: str
    shape: ChartShape | None
    width: int | None
    height: int | None
    estimate: SizingEstimate | None = None
    problem: str | None = None
    skipped: str | None = None


@dataclass(frozen=True)
class SizingReport:
    """The checked components of a dashboard, in layout order."""
    dashboard_id: int
    components: tuple[ComponentSizing, ...] = field(default=())

    @property
    def problems(self) -> list[ComponentSizing]:
        return [component for component in self.components if component.problem]

    def summary(self) -> str:
        """One line per component: height, estimated range and the problem or why it was skipped."""
        lines = []
        for item in self.components:
            if item.estimate is None:
                lines.append(f"{item.title}: not checked ({item.skipped})")
                continue
            span = f"{item.estimate.min_units}-{item.estimate.max_units} (recommended {item.estimate.recommended_units})"
            lines.append(f"{item.title}: height {item.height}, content {span}"
                         + (f": {item.problem}" if item.problem else ": ok")
                         + (" [approximate]" if item.estimate.approximate else ""))
        return "\n".join(lines)


def _column_name(column: object) -> str | None:
    """Name of a column in the chart data: a column name, or the label of an adhoc column."""
    if isinstance(column, str):
        return column
    if isinstance(column, dict) and isinstance(column.get("label"), str):
        return str(column["label"])
    return None


def _distinct(rows: list[dict[str, Any]], columns: list[str]) -> list[tuple[str, ...]]:
    seen: dict[tuple[str, ...], None] = {}
    for row in rows:
        seen.setdefault(tuple(str(row.get(column, "")) for column in columns), None)
    return list(seen)


def _table_content(params: dict[str, Any], result: dict[str, Any], title: str) -> TableContent:
    """Rows and labels (first column) of a table, with its search box and pagination."""
    rows = int(result.get("rowcount") or len(result.get("data") or []))
    names = result.get("colnames") or []
    label = names[0] if names else None
    page = params.get("server_page_length") if params.get("server_pagination") else params.get("page_length")
    pagination = isinstance(page, int) and page > 0
    if isinstance(page, int) and page > 0:
        rows = min(rows, page)
    config = (params.get("column_config") or {}).get(label) or {}
    labels = [str(row.get(label, "")) for row in (result.get("data") or [])[:rows]] if label else []
    return TableContent(rows=rows, labels=labels, title=title, fixed_label_width=bool(config.get("columnWidth")),
                        search=bool(params.get("include_search")), pagination=pagination)


def _pivot_content(params: dict[str, Any], result: dict[str, Any], title: str) -> TableContent:
    """Rows of a pivot table: the distinct values of its row dimensions (plus the totals row), labeled by the last."""
    columns = [name for name in map(_column_name, params.get("groupbyRows") or []) if name]
    keys = _distinct(result.get("data") or [], columns) if columns else [()]
    totals = 1 if params.get("colTotals") else 0
    return TableContent(rows=len(keys) + totals, labels=[key[-1] for key in keys if key], title=title)


def _bars_content(params: dict[str, Any], result: dict[str, Any], title: str) -> BarsContent:
    """Bars of a horizontal bar chart: the distinct values of its x axis (the categories)."""
    axis = _column_name(params.get("x_axis"))
    keys = _distinct(result.get("data") or [], [axis]) if axis else []
    return BarsContent(bars=len(keys), labels=[key[0] for key in keys], title=title,
                       legend=params.get("show_legend", True) is not False)


_CONTENT: dict[ChartShape, Callable[[dict[str, Any], dict[str, Any], str], TableContent | BarsContent]] = {
    ChartShape.TABLE: _table_content, ChartShape.PIVOT_TABLE: _pivot_content, ChartShape.HORIZONTAL_BARS: _bars_content,
}


class DashboardSizing:
    """Sizing check of saved dashboards (available as `client.dashboard_sizing`); it never writes."""

    def __init__(self, client: _Client) -> None:
        self.client = client

    def check(self, dashboard_id: int, profile: SizingProfile | None = None, max_rows: int | None = None,
              warn: bool = True) -> SizingReport:
        """Checks each chart and markdown component of the dashboard against its content.

        Args:
            dashboard_id: the dashboard.
            profile: the measures (default: the calibrated profile of the target Superset version, default theme).
            max_rows: rows (or bars) above which a table stops growing and scrolls; None: every row counts.
            warn: emit a SizingWarning for each component whose height does not fit.
        """
        profile = profile or calibrated_profile()
        dashboard = self.client.dashboards.get(dashboard_id)
        layout: DashboardLayout = dashboard.position_json
        metadata = dashboard.json_metadata
        filter_bar = isinstance(metadata, Metadata) and bool(metadata.native_filter_configuration) and \
            str(metadata.filter_bar_orientation or "VERTICAL") == "VERTICAL"
        items = []
        for component_id in _in_layout_order(layout):
            data = layout.components[component_id]
            item = self._check_component(component_id, data, profile, max_rows, filter_bar)
            if item.problem and warn:
                warnings.warn(f"{item.title}: {item.problem}", SizingWarning, stacklevel=2)
            items.append(item)
        return SizingReport(dashboard_id, tuple(items))

    def _check_component(self, component_id: str, data: dict[str, Any], profile: SizingProfile,
                         max_rows: int | None, filter_bar: bool) -> ComponentSizing:
        meta = data.get("meta") or {}
        width, height = meta.get("width"), meta.get("height")
        if data.get("type") == "MARKDOWN":
            title = f"markdown {component_id}"
            shape: ChartShape | None = ChartShape.MARKDOWN
            content: Content | str = str(meta.get("code") or "")
            columns = 0
        else:
            title = str(meta.get("sliceNameOverride") or meta.get("sliceName") or component_id)
            shape, content, columns = self._chart_content(meta.get("chartId"), title)
        # A chart's reason for not being checked is a str too: only markdown content is text.
        if shape is None or isinstance(content, str) and shape is not ChartShape.MARKDOWN:
            return ComponentSizing(component_id, title, shape, width, height, skipped=str(content))
        if not isinstance(width, int) or not isinstance(height, int):
            return ComponentSizing(component_id, title, shape, width, height, skipped="no width or height stored")
        result = estimate(shape, content, profile, Layout(columns=width, vertical_filter_bar=filter_bar), max_rows)
        if shape is ChartShape.TABLE and columns > 2:
            # Only the label column's wrapping is known: other text columns may wrap too in a narrow chart.
            result = replace(result, approximate=True, reasons=(
                *result.reasons, f"{columns} columns: rows may be taller where columns other than the label wrap"))
        return ComponentSizing(component_id, title, shape, width, height, result, result.problem(height))

    def _chart_content(self, chart_id: object, title: str) -> tuple[ChartShape | None, Content | str, int]:
        """The shape, content and number of data columns of a chart, or (shape, why it is not checked, 0)."""
        if not isinstance(chart_id, int):
            return None, "no chart id", 0
        try:
            chart = self.client.charts.get(chart_id)
        except UnsupportedTypeError as error:
            return None, f"viz_type without a model ({error})", 0
        if not isinstance(chart, Chart):
            return None, "viz_type without a model", 0
        params = chart.params.to_dict()
        shape = chart_shape(params)
        if shape is None:
            return None, f"{params.get('viz_type')} is not covered by the sizing formulas", 0
        url = self.client.join_urls(self.client.charts.base_url, "data")
        try:
            results = self.client.post(url, json=chart.ui_query_context()).json().get("result") or []
        except BadRequestError as error:  # e.g. a chart whose query Superset refuses: reported, not raised
            return shape, f"the chart data API refused its query ({error})", 0
        if not results:
            return shape, "the chart data API returned no result", 0
        return shape, _CONTENT[shape](params, results[0], title), len(results[0].get("colnames") or [])


def _in_layout_order(layout: DashboardLayout) -> list[str]:
    """Chart and markdown components in tree order (as on the dashboard)."""
    found: list[str] = []

    def visit(component_id: str) -> None:
        component = layout.components.get(component_id) or {}
        if component.get("type") in ("CHART", "MARKDOWN"):
            found.append(component_id)
        for child in component.get("children") or []:
            visit(child)

    visit("ROOT_ID")
    return found

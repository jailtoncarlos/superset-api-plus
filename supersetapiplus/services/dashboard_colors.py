"""Labels the charts of a saved dashboard ask the categorical color scale for (available as ``client.dashboard_colors``).

The dashboard frontend (Superset 6.1.0) stores a color per label (``json_metadata.map_label_colors``) and the labels
drawn by two or more charts (``shared_label_colors``). Filling them needs the labels each chart registers, which
depend on the data: this service reads each chart's data through ``POST /api/v1/chart/data`` with the query the
Superset UI builds from its params and applies the label rules of its plugin (:mod:`supersetapiplus.charts.color_labels`).
It never writes.
"""
from __future__ import annotations

from typing import Any, Protocol

import requests

from supersetapiplus.charts.charts import Chart, Charts
from supersetapiplus.charts.color_labels import LABEL_RULES, color_labels
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.exceptions import UnsupportedTypeError
from supersetapiplus.resources.datasets import Datasets


class _Client(Protocol):
    """What the service needs from SupersetClient (a protocol: services must not import the client layer)."""
    charts: Charts
    dashboards: Dashboards
    datasets: Datasets

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        ...

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        ...

    @staticmethod
    def join_urls(*args: object) -> str:
        ...


class DashboardColors:
    """Color labels of saved charts and dashboards (available as `client.dashboard_colors`); it never writes."""

    def __init__(self, client: _Client) -> None:
        self.client = client

    def chart_labels(self, chart: Chart | int) -> list[str] | None:
        """The labels the saved `chart` (or chart id) registers in the categorical color scale of a dashboard, from
        its current data; None for a viz_type that registers none (tables, big numbers, sequential colors). Raises
        UnsupportedTypeError for a viz_type the library does not model."""
        if isinstance(chart, int):
            loaded = self.client.charts.get(chart)
            if not isinstance(loaded, Chart):
                raise UnsupportedTypeError(f"chart {chart} has a viz_type without a model")
            chart = loaded
        params = chart.explore_params()  # as the plugin sees them
        if LABEL_RULES.get(str(params.get("viz_type")), ...) is None:
            return None
        url = self.client.join_urls(self.client.charts.base_url, "data")
        results = self.client.post(url, json=chart.ui_query_context()).json().get("result") or []
        return color_labels(params, results, self._verbose_map(chart))

    def dashboard_labels(self, dashboard_id: int) -> dict[int, list[str]]:
        """Chart id -> labels, for the charts of the saved dashboard that register labels (the input of the label
        color table of the dashboard)."""
        url = self.client.join_urls(self.client.dashboards.base_url, dashboard_id, "charts")
        labels: dict[int, list[str]] = {}
        for item in self.client.get(url).json()["result"]:
            chart_labels = self.chart_labels(int(item["id"]))
            if chart_labels is not None:
                labels[int(item["id"])] = chart_labels
        return labels

    def _verbose_map(self, chart: Chart) -> dict[str, str]:
        """The dataset's verbose names (column or metric name -> verbose name), as the frontend datasource has them."""
        if chart.datasource_type != "table" or not isinstance(chart.datasource_id, int):
            return {}
        result = self.client.get(self.client.datasets.object_url(chart.datasource_id)).json()["result"]
        verbose: dict[str, str] = {}
        for items, name_key in ((result.get("columns") or [], "column_name"), (result.get("metrics") or [],
                                                                                 "metric_name")):
            for item in items:
                if isinstance(item, dict) and item.get(name_key) and item.get("verbose_name"):
                    verbose[str(item[name_key])] = str(item["verbose_name"])
        return verbose

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
from supersetapiplus.charts.explore import DatasetTime
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
        UnsupportedTypeError for a viz_type the library does not model, NotImplementedError when Superset answers
        the chart data asynchronously (``GLOBAL_ASYNC_QUERIES``)."""
        if isinstance(chart, int):
            loaded = self.client.charts.get(chart)
            if not isinstance(loaded, Chart):
                raise UnsupportedTypeError(f"chart {chart} has a viz_type without a model")
            chart = loaded
        dataset = self._dataset(chart)
        if dataset is not None:  # Explore normalizes the params with the dataset's temporal columns
            chart.use_dataset_time(DatasetTime(
                columns=tuple(str(c["column_name"]) for c in dataset.get("columns") or [] if c.get("is_dttm")),
                main=dataset.get("main_dttm_col")))
        params = chart.explore_params()  # as the plugin sees them
        if LABEL_RULES.get(str(params.get("viz_type")), ...) is None:
            return None
        url = self.client.join_urls(self.client.charts.base_url, "data")
        response = self.client.post(url, json=chart.ui_query_context())
        if response.status_code == 202:  # GLOBAL_ASYNC_QUERIES: a job, not the data (charts/data/api.py)
            raise NotImplementedError("Superset ran the chart query asynchronously (202); the labels need its data: "
                                      "use an instance without GLOBAL_ASYNC_QUERIES or a cached chart.")
        results = response.json().get("result") or []
        return color_labels(params, results, self._verbose_map(dataset))

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

    def _dataset(self, chart: Chart) -> dict[str, Any] | None:
        """The chart's dataset as the API returns it (None for another datasource type)."""
        if chart.datasource_type != "table" or not isinstance(chart.datasource_id, int):
            return None
        result: dict[str, Any] = self.client.get(self.client.datasets.object_url(chart.datasource_id)).json()["result"]
        return result

    @staticmethod
    def _verbose_map(dataset: dict[str, Any] | None) -> dict[str, str]:
        """The dataset's verbose names (column or metric name -> verbose name), as the frontend datasource has them."""
        verbose: dict[str, str] = {}
        if dataset is None:
            return verbose
        for items, name_key in ((dataset.get("columns") or [], "column_name"), (dataset.get("metrics") or [],
                                                                                  "metric_name")):
            for item in items:
                if isinstance(item, dict) and item.get(name_key) and item.get("verbose_name"):
                    verbose[str(item[name_key])] = str(item["verbose_name"])
        return verbose

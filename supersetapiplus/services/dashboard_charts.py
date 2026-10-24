"""Charts and dashboards together: association, placement in the layout and creation-and-attachment.

Available as ``client.dashboard_charts``; ``Charts.add_to_dashboard``, ``Charts.add_and_attach_to_dashboard``,
``Dashboards.attach_charts`` and ``Dashboard.add_chart`` delegate here.
"""
from typing import Any, Protocol

import requests

from supersetapiplus.charts.charts import Chart, Charts
from supersetapiplus.dashboards.dashboards import Dashboard, Dashboards
from supersetapiplus.exceptions import ChartValidationError, DashboardValidationError


class _Client(Protocol):
    """What the service needs from SupersetClient (a protocol: services must not import the client layer)."""
    charts: Charts
    dashboards: Dashboards

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        ...


class DashboardCharts:
    """Operations on charts and dashboards together (available as `client.dashboard_charts`)."""
    def __init__(self, client: _Client) -> None:
        self.client = client

    def add_to_dashboard(self, chart: Chart | int, dashboard_id: int) -> list[int]:
        """
        Associates the chart with the dashboard (PUT /chart/{pk} with only `dashboards`), keeping existing associations.

        The association is by id on the chart: the `dashboards` field of ChartPutSchema replaces the list,
        so the current ones are read first. Returns the stored list.
        """
        chart_id = chart if isinstance(chart, int) else chart.id
        if not chart_id:
            raise ChartValidationError('Save the chart before attaching it to a dashboard (chart.id is empty).')
        charts = self.client.charts
        current: list[int] = charts.dashboard_ids(chart_id)
        if dashboard_id in current:
            return current
        updated = current + [dashboard_id]
        self.client.put(charts.object_url(chart_id), json={"dashboards": updated})
        return updated

    def attach_charts(self, dashboard: Dashboard) -> list[int]:
        """
        Associates with the dashboard, in Superset, every chart present in its layout (position_json).

        Call after the dashboard has an id; charts already associated are not rewritten.
        """
        if not dashboard.id:
            raise DashboardValidationError('Save the dashboard before attaching charts (dashboard.id is empty).')
        chart_ids: list[int] = dashboard.position.chart_ids()
        for chart_id in chart_ids:
            self.add_to_dashboard(chart_id, dashboard.id)
        return chart_ids

    def add_chart(self, dashboard: Dashboard, chart: Chart, title: str | None = None, parent: Any = None,
                  **placement: Any) -> None:
        """
        Places the chart in the dashboard layout and associates it with the dashboard in Superset.

        The dashboard must be saved (have an id). A chart without an id is created first. The association
        is made by a PUT on the chart; the layout and json_metadata are only stored on the dashboard's
        next save(). `placement` takes the layout options (height, width, id).
        """
        if not dashboard.id:
            raise DashboardValidationError('To add charts, first save the dashboard. Do this by calling the '
                                           'client.dashboards.add([this-dashboard]) method.')
        if not chart.id:
            self.client.charts.add(chart)
        dashboard.metadata.add_chart(chart)
        dashboard.position.add_chart(chart, title=title, parent=parent, **placement)
        self.add_to_dashboard(chart, dashboard.id)

    def add_and_attach_to_dashboard(self, chart: Chart, title: str, parent: Any = None) -> int:
        """
        Creates the chart and places it in the layout of the dashboard the source chart belongs to.

        Args:
            chart (Chart): chart to create (e.g. a clone of a chart already associated with a dashboard).
            title (str): title shown on the dashboard (sliceNameOverride).
            parent (optional): layout component to insert into.

        Returns:
            int: id of the created chart.

        Raises:
            DashboardValidationError: the source chart does not belong to any dashboard.
        """
        # Validate before creating: previously the chart was created and left orphaned when validation failed.
        if not chart.dashboards:
            raise DashboardValidationError(
                message="Could not attach the chart: it does not belong to any dashboard.",
                solution="Check that the given chart is associated with a dashboard before calling this method."
            )
        source_id = chart.dashboards[0].id
        if source_id is None:
            raise DashboardValidationError("The dashboard of the source chart has no id.")
        dashboard = self.client.dashboards.get(source_id)
        new_id: int = self.client.charts.add(chart)
        self.add_chart(dashboard, chart, title, parent)
        dashboard.save()
        return new_id

"""Dashboards."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, SerializableModel, UnsupportedObject
from supersetapiplus.base.fields import object_field
from supersetapiplus.dashboards.layout import DashboardLayout
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.exceptions import DashboardValidationError, UnsupportedTypeError
from supersetapiplus.typing import SerializableOptional


def defult_metadata():
    return Metadata()


def defult_metadata_position():
    return DashboardLayout.empty()


@dataclass
class Dashboard(SerializableModel):
    JSON_FIELDS = ['json_metadata', 'position_json']
    PRESERVE_EXTRA_FIELDS = False
    # Fields accepted by the API (OpenAPI 6.1.0: DashboardRestApi.post / DashboardRestApi.put).
    POST_FIELDS = (
        "certification_details", "certified_by", "css", "dashboard_title", "external_url",
        "is_managed_externally", "json_metadata", "owners", "position_json", "published", "roles", "slug",
    )
    PUT_FIELDS = (
        "certification_details", "certified_by", "css", "dashboard_title", "external_url",
        "is_managed_externally", "json_metadata", "owners", "position_json", "published", "roles", "slug",
        "tags",
    )

    dashboard_title: str = ''

    published: SerializableOptional[bool] = field(default=None)
    id: int | None = field(default=None)
    css: SerializableOptional[str] = field(default=None)
    slug: SerializableOptional[str] = field(default=None)

    json_metadata: Metadata = object_field(cls=Metadata, default_factory=Metadata)
    position_json: SerializableOptional[DashboardLayout] = object_field(cls=DashboardLayout,
                                                                        default_factory=DashboardLayout.empty)

    def __post_init__(self):
        super().__post_init__()
        self._charts_slice_names = []

    @classmethod
    def from_json(cls, data: dict):
        obj = super().from_json(data)
        obj._charts_slice_names = obj._extra_fields.get('charts', [])
        return obj

    @property
    def charts_slice_names(self):
        return self._charts_slice_names

    @property
    def metadata(self):
        return self.json_metadata

    @property
    def position(self):
        return self.position_json

    def reset_layout(self) -> DashboardLayout:
        """Replaces the layout with an empty one (root, grid and title header); returns the new layout."""
        self.position_json = DashboardLayout.empty(self.dashboard_title)
        return self.position_json

    def to_dict(self, columns: list = None, convert_to_json: bool = False) -> dict:
        # Native filter scopes (chartsInScope/tabsInScope) are derived from the layout, as the editor does.
        if isinstance(self.position_json, DashboardLayout):
            if self.position_json.created_by_library:
                self.position_json.set_title(self.dashboard_title)
            if isinstance(self.json_metadata, Metadata):
                self.json_metadata.update_native_filter_scopes(self.position_json)
        return super().to_dict(columns, convert_to_json)

    def add_chart(self, chart, title: str, parent=None, height: int = 50, width: int = 4, id: str | None = None):
        """
        Places the chart in the layout and associates it with this dashboard in Superset.

        The dashboard must be saved (have an id). A chart without an id is created first. The association
        is made by a PUT on the chart (Charts.add_to_dashboard); the layout and json_metadata are only
        stored on the dashboard's next save().
        """
        if not self.id:
            raise DashboardValidationError('To add charts, first save the dashboard. Do this by calling the '
                                           'client.dashboards.add([this-dashboard]) method.')
        charts = self._factory.client.charts
        if not chart.id:
            charts.add(chart)

        self.metadata.add_chart(chart)
        self.position.add_chart(chart, title=title, parent=parent, height=height, width=width, id=id)
        charts.add_to_dashboard(chart, self.id)

    @property
    def colors(self) -> dict:
        """Get dashboard color mapping."""
        return self.json_metadata.label_colors

    @colors.setter
    def colors(self, value: dict) -> None:
        """Set dashboard color mapping."""
        self.json_metadata.label_colors = dict(value)

    def update_colors(self, value: dict) -> None:
        """Update dashboard colors."""
        colors = self.colors
        colors.update(value)
        self.colors = colors

    def get_charts(self) -> list:
        """Charts associated with the dashboard in Superset (GET /dashboard/{id}/charts), as library objects."""
        client = self._factory.client
        url = client.join_urls(self._factory.base_url, self.id, "charts")
        charts = []
        for item in client.get(url).json()["result"]:
            try:
                charts.append(client.charts.get(item["id"]))
            except UnsupportedTypeError:
                charts.append(UnsupportedObject(item, factory=client.charts))
        return charts

    def delete(self, exclude_charts: bool = False) -> bool:
        """Deletes the dashboard; with exclude_charts=True, also deletes the associated charts."""
        charts = self.get_charts() if exclude_charts else []
        deleted = self._factory.delete(id=self.id)
        if deleted:
            for chart in charts:
                self._factory.client.charts.delete(chart.id)
        return deleted


class Dashboards(ApiModelFactories):
    endpoint = "dashboard/"

    def attach_charts(self, dashboard: Dashboard) -> list[int]:
        """
        Associates with the dashboard, in Superset, every chart present in its layout (position_json).

        Call after the dashboard has an id; charts already associated are not rewritten.
        """
        if not dashboard.id:
            raise DashboardValidationError('Save the dashboard before attaching charts (dashboard.id is empty).')
        chart_ids = dashboard.position.chart_ids()
        for chart_id in chart_ids:
            self.client.charts.add_to_dashboard(chart_id, dashboard.id)
        return chart_ids

    def _default_object_class(self) -> type[SerializableModel]:
        return Dashboard

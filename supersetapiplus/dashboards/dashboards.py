"""Dashboards."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, SerializableModel
from supersetapiplus.base.fields import object_field
from supersetapiplus.dashboards.itemposition import ItemPosition
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.dashboards.metadataposition import Metadataposition
from supersetapiplus.dashboards.nodeposisition import RowNodePosition
from supersetapiplus.exceptions import DashboardValidationError
from supersetapiplus.typing import SerializableOptional


def defult_metadata():
    return Metadata()


def defult_metadata_position():
    return Metadataposition()


@dataclass
class Dashboard(SerializableModel):
    JSON_FIELDS = ['json_metadata', 'position_json']
    PRESERVE_EXTRA_FIELDS = False
    # Campos aceitos pela API (OpenAPI 6.1.0: DashboardRestApi.post / DashboardRestApi.put).
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
    position_json: SerializableOptional(Metadataposition) = object_field(cls=Metadataposition,
                                                                         default_factory=Metadataposition)
    # charts: List[Chart] = field(default_factory=Chart)

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

    def add_chart(self, chart, title: str, parent: ItemPosition = None, height: int = 50, width: int = 4,
                  relocate: bool = True):
        chart.add_dashboard(self)
        if not self.id:
            raise DashboardValidationError('To add charts, first save the dashboard. Do this by calling the '
                                           'client.dashboards.add([this-dashboard]) method.')

        if not chart.id:
            self._factory.client.charts.add(chart)

        self._factory.client.charts.add_to_dashboard(chart, self.id)

        self.metadata.add_chart(chart)

        node_position = parent
        if node_position is None:
            if not node_position:
                grid = self.position.tree.grid
                node_position = grid
                if grid.children:
                    node_position = grid.children[-1]
                if not isinstance(node_position, RowNodePosition):
                    node_position = grid
        self.position.add_chart(chart, title, node_position, height, width, relocate)

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

    def get_charts(self) -> list[int]:
        """Get chart objects"""
        #http://localhost:8088/api/v1/dashboard/21/charts
        charts = []
        for slice_name in self.charts_slice_names:
            c = self._factory.client.charts.find_one(slice_name=slice_name)
            charts.append(c)
        return charts

    def delete(self, exclude_charts:bool = False) -> bool:
        deleted = self._factory.delete(id=self.id)
        if deleted and exclude_charts:
            for chart in self.get_charts():
                chart.delete()


class Dashboards(ApiModelFactories):
    endpoint = "dashboard/"

    def _default_object_class(self) -> type[SerializableModel]:
        return Dashboard

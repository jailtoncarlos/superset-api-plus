"""Dashboards."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, SerializableModel, UnsupportedObject
from supersetapiplus.base.fields import object_field
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.dashboards.metadataposition import Metadataposition
from supersetapiplus.dashboards.nodeposisition import RowNodePosition
from supersetapiplus.exceptions import DashboardValidationError, UnsupportedTypeError
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
    position_json: SerializableOptional[Metadataposition] = object_field(cls=Metadataposition,
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

    def add_chart(self, chart, title: str, parent=None, height: int = 50, width: int = 4, relocate: bool = True):
        """
        Coloca o gráfico no layout e o associa a este dashboard no Superset.

        O dashboard precisa estar salvo (ter id). Gráfico sem id é criado antes. A associação é feita
        por PUT no gráfico (Charts.add_to_dashboard); o layout e o json_metadata só são gravados no
        próximo save() do dashboard.
        """
        if not self.id:
            raise DashboardValidationError('To add charts, first save the dashboard. Do this by calling the '
                                           'client.dashboards.add([this-dashboard]) method.')
        charts = self._factory.client.charts
        if not chart.id:
            charts.add(chart)

        self.metadata.add_chart(chart)
        self.position.add_chart(chart, title, parent or self._ultima_linha_ou_grid(), height, width, relocate)
        charts.add_to_dashboard(chart, self.id)

    def _ultima_linha_ou_grid(self):
        grid = self.position.tree.grid
        ultima = grid.children[-1] if grid.children else None
        return ultima if isinstance(ultima, RowNodePosition) else grid

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
        """Gráficos associados ao dashboard no Superset (GET /dashboard/{id}/charts), como objetos da lib."""
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
        """Remove o dashboard; com exclude_charts=True, remove também os gráficos associados."""
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
        Associa ao dashboard, no Superset, todos os gráficos presentes no seu layout (position_json).

        Chamar depois de o dashboard ter id; os gráficos já associados não são regravados.
        """
        if not dashboard.id:
            raise DashboardValidationError('Save the dashboard before attaching charts (dashboard.id is empty).')
        chart_ids = dashboard.position.tree.chart_ids()
        for chart_id in chart_ids:
            self.client.charts.add_to_dashboard(chart_id, dashboard.id)
        return chart_ids

    def _default_object_class(self) -> type[SerializableModel]:
        return Dashboard

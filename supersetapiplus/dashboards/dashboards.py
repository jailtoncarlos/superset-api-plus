"""Dashboards."""
from dataclasses import dataclass, field
from typing import Any

from typing_extensions import Self

from supersetapiplus.core.fields import object_field
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.dashboards.layout import DashboardLayout
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.deprecation import module_aliases
from supersetapiplus.exceptions import DashboardValidationError, UnsupportedTypeError
from supersetapiplus.resources.repository import ApiModelFactories, UnsupportedObject


def default_metadata() -> Metadata:
    return Metadata()


def default_metadata_position() -> DashboardLayout:
    return DashboardLayout.empty()


@dataclass
class Dashboard(SerializableModel):
    """A dashboard: title, layout (`position_json`, see DashboardLayout), `json_metadata` (native filters,
    colors, cross-filters), owners and roles. Read with `client.dashboards.get()`, create with `add()`."""
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

    ID_REFERENCE_FIELDS = ("owners", "roles")

    dashboard_title: str = ''

    published: SerializableOptional[bool] = field(default=None)
    id: int | None = field(default=None)
    css: SerializableOptional[str] = field(default=None)
    slug: SerializableOptional[str] = field(default=None)
    # Users (owners) and roles (dashboard RBAC) as read from Superset, or their ids; sent as ids.
    # Absent on create unless set: Superset then makes the current user the owner.
    owners: SerializableOptional[list[Any]] = field(default=None)
    roles: SerializableOptional[list[Any]] = field(default=None)
    certified_by: SerializableOptional[str] = field(default=None)
    certification_details: SerializableOptional[str] = field(default=None)
    external_url: SerializableOptional[str] = field(default=None)
    is_managed_externally: SerializableOptional[bool] = field(default=None)

    json_metadata: Metadata = object_field(cls=Metadata, default_factory=Metadata)
    position_json: SerializableOptional[DashboardLayout] = object_field(cls=DashboardLayout,
                                                                        default_factory=DashboardLayout.empty)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._charts_slice_names: list[str] = []

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        obj = super().from_json(data)
        obj._charts_slice_names = obj._extra_fields.get('charts', [])
        return obj

    @property
    def charts_slice_names(self) -> list[str]:
        return self._charts_slice_names

    @property
    def metadata(self) -> Metadata:
        return self.json_metadata

    @property
    def position(self) -> DashboardLayout:
        """The layout (`position_json`); a dashboard stored without one gets an empty layout."""
        if not isinstance(self.position_json, DashboardLayout):
            self.position_json = DashboardLayout.empty(self.dashboard_title)
        return self.position_json

    def reset_layout(self) -> DashboardLayout:
        """Replaces the layout with an empty one (root, grid and title header); returns the new layout."""
        self.position_json = DashboardLayout.empty(self.dashboard_title)
        return self.position_json

    def to_dict(self, columns: list[str] | None = None, convert_to_json: bool = False) -> dict[str, Any]:
        # Native filter scopes (chartsInScope/tabsInScope) are derived from the layout, as the editor does.
        if isinstance(self.position_json, DashboardLayout):
            if self.position_json.created_by_library:
                self.position_json.set_title(self.dashboard_title)
            if isinstance(self.json_metadata, Metadata):
                self.json_metadata.update_native_filter_scopes(self.position_json)
        return super().to_dict(columns, convert_to_json)

    def add_chart(self, chart: Any, title: str, parent: Any = None, height: int = 50, width: int = 4,
                  id: str | None = None) -> None:
        """Places the chart in the layout and associates it with this dashboard in Superset (see DashboardCharts).

        The dashboard must be saved (have an id); a chart without an id is created first.
        """
        if not self.id:
            raise DashboardValidationError('To add charts, first save the dashboard. Do this by calling the '
                                           'client.dashboards.add([this-dashboard]) method.')
        self._repository().client.dashboard_charts.add_chart(self, chart, title, parent, height=height, width=width,
                                                             id=id)

    @property
    def colors(self) -> dict[str, str]:
        """Get dashboard color mapping."""
        return self.json_metadata.label_colors

    @colors.setter
    def colors(self, value: dict[str, str]) -> None:
        """Set dashboard color mapping."""
        self.json_metadata.label_colors = dict(value)

    def update_colors(self, value: dict[str, str]) -> None:
        """Update dashboard colors."""
        colors = self.colors
        colors.update(value)
        self.colors = colors

    def get_charts(self) -> list[Any]:
        """Charts associated with the dashboard in Superset (GET /dashboard/{id}/charts), as library objects."""
        client = self._repository().client
        url = client.join_urls(self._repository().base_url, self.id, "charts")
        charts: list[Any] = []
        for item in client.get(url).json()["result"]:
            try:
                charts.append(client.charts.get(item["id"]))
            except UnsupportedTypeError:
                charts.append(UnsupportedObject(item, factory=client.charts))
        return charts

    def delete(self, exclude_charts: bool = False) -> bool:
        """Deletes the dashboard; with exclude_charts=True, also deletes the associated charts."""
        charts = self.get_charts() if exclude_charts else []
        deleted: bool = self._repository().delete(id=self.id)
        if deleted:
            for chart in charts:
                self._repository().client.charts.delete(chart.id)
        return deleted


class Dashboards(ApiModelFactories):
    endpoint = "dashboard/"

    def copy(self, dashboard: Dashboard | int | str, dashboard_title: str | None = None,
             duplicate_slices: bool = False, css: str | None = None) -> int:
        """Copy a dashboard (an object, its id or its slug); returns the id of the copy.

        `duplicate_slices` also copies its charts (otherwise the copy shows the same charts). The copy keeps
        the json_metadata of the original (required by DashboardCopySchema).
        """
        source_id = dashboard.id if isinstance(dashboard, Dashboard) else dashboard
        if source_id is None:
            raise DashboardValidationError("Save the dashboard before copying it (dashboard.id is empty).")
        source = dashboard if isinstance(dashboard, Dashboard) else self.get(source_id)
        payload = {"json_metadata": source.to_json()["json_metadata"], "duplicate_slices": duplicate_slices,
                   "dashboard_title": dashboard_title or f"{source.dashboard_title} (copy)"}
        if css is not None:
            payload["css"] = css
        response = self.client.post(self.client.join_urls(self.base_url, source.id, "copy/"), json=payload)
        new_id: int = response.json()["result"]["id"]
        return new_id

    def attach_charts(self, dashboard: Dashboard) -> list[int]:
        """Associates with the dashboard every chart present in its layout (see DashboardCharts)."""
        attached: list[int] = self.client.dashboard_charts.attach_charts(dashboard)
        return attached

    def _default_object_class(self) -> type[SerializableModel]:
        return Dashboard


# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"defult_metadata": "default_metadata",
    "defult_metadata_position": "default_metadata_position"})

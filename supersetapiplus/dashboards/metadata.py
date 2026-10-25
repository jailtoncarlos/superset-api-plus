from collections.abc import Iterable, Sequence
from typing import Any, ClassVar, TypeAlias

from pydantic import Field, PrivateAttr

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.enums import StringEnum
from supersetapiplus.core.references import DatasetRef, SavedChart
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.dashboards import native_filters
from supersetapiplus.dashboards.layout import DashboardLayout
from supersetapiplus.deprecation import module_aliases

#: The parent filters of a native filter: a filter returned by add_native_filter (or its id), a list of them, or None.
FilterParent: TypeAlias = "native_filters.NativeFilterItem | str | Sequence[native_filters.NativeFilterItem | str] | None"


class FilterBarOrientation(StringEnum):
    """Position of the native filter bar (superset-frontend/src/dashboard/types.ts, Superset 6.1.0)."""
    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"


class CrossFilters(ApiModel):
    scope: str = 'global'
    chartsInScope: list[int] = Field(default_factory=list)


class ChartConfiguration(ApiModel):
    id: int | None = None
    crossFilters: CrossFilters = Field(default_factory=CrossFilters)


class GlobalChartConfigurationScope(ApiModel):
    # Default cross-filter scope in the frontend (DEFAULT_CROSS_FILTER_SCOPING): the whole dashboard.
    rootPath: list[str] = Field(default_factory=lambda: ['ROOT_ID'])
    excluded: list[int] = Field(default_factory=list)  # chart ids (NativeFilterScope.excluded: number[])


class GlobalChartConfiguration(ApiModel):
    scope: GlobalChartConfigurationScope = Field(default_factory=GlobalChartConfigurationScope)
    chartsInScope: list[int] = Field(default_factory=list)  # chart ids


class Metadata(ApiModel):
    """`json_metadata` of a dashboard (DashboardJSONMetadataSchema, Superset 6.1.0); unmodeled keys are kept."""
    JSON_FIELDS: ClassVar[list[str]] = ['default_filters']

    color_scheme: str = Field(default='', repr=False)
    refresh_frequency: int = 0
    # List of labels in 6.x (SharedLabelsColorsField discards dicts).
    shared_label_colors: list[str] = Field(default_factory=list)
    color_scheme_domain: list[str] = Field(default_factory=list)
    expanded_slices: dict[str, Any] = Field(default_factory=dict)
    label_colors: dict[str, str] = Field(default_factory=dict)
    timed_refresh_immune_slices: list[int] = Field(default_factory=list)
    cross_filters_enabled: bool = False
    filter_scopes: SerializableOptional[dict[str, Any]] = Field(default_factory=dict)
    chart_configuration: dict[str, ChartConfiguration] = Field(default_factory=dict)
    global_chart_configuration: GlobalChartConfiguration = Field(default_factory=GlobalChartConfiguration)
    default_filters: SerializableOptional[dict[str, Any]] = None

    # List of native filters and dividers, kept as the dicts Superset stores (see native_filters).
    native_filter_configuration: SerializableOptional[list[dict[str, Any]]] = None

    # Other keys of DashboardJSONMetadataSchema (6.1.0); absent unless read or set.
    color_namespace: SerializableOptional[str] = None
    map_label_colors: SerializableOptional[dict[str, str]] = None
    positions: SerializableOptional[dict[str, Any]] = None
    filter_bar_orientation: SerializableOptional[FilterBarOrientation] = None
    show_chart_timestamps: SerializableOptional[bool] = None
    chart_customization_config: SerializableOptional[list[dict[str, Any]]] = None
    stagger_refresh: SerializableOptional[bool] = None
    stagger_time: SerializableOptional[int] = None

    # Ids of the native filter items created by the library: only their scopes are recomputed.
    _library_filter_ids: set[str] = PrivateAttr(default_factory=set)
    # Filter id -> chart ids in scope, for filters restricted to some charts (excluded = the others).
    _filter_charts: dict[str, list[int]] = PrivateAttr(default_factory=dict)

    def clear_native_filters(self) -> None:
        self.native_filter_configuration = []
        self._library_filter_ids = set()
        self._filter_charts = {}

    def add_filter_divider(self, title: str, description: str = "",
                           id: str | None = None) -> native_filters.NativeFilterItem:
        """Section divider in the native filter bar."""
        return self._add_native_item(native_filters.divider_config(title, description, id))

    def add_native_filter(self, name: str, dataset: DatasetRef | None = None, column: str | None = None,
                          parent: FilterParent = None, charts: Iterable[SavedChart | int] | None = None,
                          excluded_charts: Iterable[SavedChart | int] | None = None,
                          **options: Any) -> native_filters.NativeFilterItem:
        """Native filter on `column` of `dataset` (a saved Dataset, its id or its uuid).

        Without `dataset` the filter has no target (``targets: [{}]``), e.g.
        ``add_native_filter("Period", filter_type=FilterType.TIME)``.
        `parent` is a filter (or a list of filters) returned by this method: the new filter depends on them
        (``cascadeParentIds``). The filter applies to every chart of the dashboard, or only to `charts`, or
        to all but `excluded_charts` (charts or chart ids). Other options are those of
        :func:`native_filters.filter_config`, for example ``adhoc_filters=[...]``, ``multiSelect=True``,
        ``inverseSelection=True`` or ``default_value=["North"]`` (the selection when the dashboard opens).
        A `dataset` read from Superset (with its columns) has the column checked: it must exist, and be
        numeric for a range filter. ``client.dashboard_charts.native_filter_problems(dashboard)`` checks the
        datasets of the charts in scope.
        """
        if charts is not None and excluded_charts is not None:
            raise ValueError("pass either charts or excluded_charts, not both.")
        parents: list[native_filters.NativeFilterItem | str] = (
            [parent] if isinstance(parent, (str, native_filters.NativeFilterItem)) else list(parent or []))
        item = self._add_native_item(native_filters.filter_config(name, dataset, column, parents, **options))
        if charts is not None:
            self._filter_charts[item.id] = [_chart_id(chart) for chart in charts]
        elif excluded_charts is not None:
            item.config["scope"]["excluded"] = [_chart_id(chart) for chart in excluded_charts]
        return item

    def update_native_filter_scopes(self, layout: DashboardLayout) -> None:
        """Sets chartsInScope/tabsInScope of the items created by the library from the dashboard layout."""
        for item in self.native_filter_configuration or []:
            if item.get("id") in self._library_filter_ids:
                if item["id"] in self._filter_charts:  # excluded depends on the charts of the layout
                    item["scope"] = native_filters.chart_scope(self._filter_charts[item["id"]], layout.chart_ids())
                scope = item.get("scope") or native_filters.root_scope()
                item["chartsInScope"], item["tabsInScope"] = layout.charts_and_tabs_in_scope(
                    scope.get("rootPath", []), scope.get("excluded", []))

    def _add_native_item(self, config: dict[str, Any]) -> native_filters.NativeFilterItem:
        if not isinstance(self.native_filter_configuration, list):
            self.native_filter_configuration = []
        self.native_filter_configuration.append(config)
        self._library_filter_ids.add(config["id"])
        return native_filters.NativeFilterItem(config)

    def add_chart(self, chart: SavedChart) -> None:
        if not isinstance(self.global_chart_configuration, GlobalChartConfiguration):
            self.global_chart_configuration = GlobalChartConfiguration()
        if not isinstance(self.global_chart_configuration.chartsInScope, list):
            self.global_chart_configuration.chartsInScope = []
        if not isinstance(self.chart_configuration, dict):
            self.chart_configuration = {}

        new_id = _chart_id(chart)
        chart_configuration = ChartConfiguration(id=new_id)
        if self.global_chart_configuration.chartsInScope:
            for chart_id in self.global_chart_configuration.chartsInScope:
                if chart_id != new_id:
                    chart_configuration.crossFilters.chartsInScope.append(chart_id)
        self.chart_configuration[str(new_id)] = chart_configuration

        self.global_chart_configuration.chartsInScope.append(new_id)


def _chart_id(chart: SavedChart | int) -> int:
    if isinstance(chart, int):
        return chart
    if chart.id is None:
        raise ValueError(f"chart {chart.slice_name!r} is not saved: it has no id.")
    return chart.id


# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"GlobalChartconfiguration": "GlobalChartConfiguration",
    "GlobalChartconfigurationScope": "GlobalChartConfigurationScope"})

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from supersetapiplus.core.enums import StringEnum
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.dashboards import native_filters
from supersetapiplus.deprecation import module_aliases


class FilterBarOrientation(StringEnum):
    """Position of the native filter bar (superset-frontend/src/dashboard/types.ts, Superset 6.1.0)."""
    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"


@dataclass
class CrossFilters(SerializableModel):
    scope: str = 'global'
    chartsInScope: list[int] = field(default_factory=list)


@dataclass
class ChartConfiguration(SerializableModel):
    id: int | None = field(default=None)
    crossFilters: CrossFilters = object_field(cls=CrossFilters, default_factory=CrossFilters)


@dataclass
class GlobalChartConfigurationScope(SerializableModel):
    # Default cross-filter scope in the frontend (DEFAULT_CROSS_FILTER_SCOPING): the whole dashboard.
    rootPath: list[str] = field(default_factory=lambda: ['ROOT_ID'])
    excluded: list[int] = field(default_factory=list)  # chart ids (NativeFilterScope.excluded: number[])


@dataclass
class GlobalChartConfiguration(SerializableModel):
    scope: GlobalChartConfigurationScope = object_field(cls=GlobalChartConfigurationScope,
                                                        default_factory=GlobalChartConfigurationScope)
    chartsInScope: list[int] = field(default_factory=list)  # chart ids


@dataclass
class Metadata(SerializableModel):
    JSON_FIELDS = ['default_filters']

    color_scheme: str = default_string()
    refresh_frequency: int = field(default=0)
    # List of labels in 6.x (SharedLabelsColorsField discards dicts).
    shared_label_colors: list[str] = field(default_factory=list)
    color_scheme_domain: list[str] = field(default_factory=list)
    expanded_slices: dict[str, Any] = field(default_factory=dict)
    label_colors: dict[str, str] = field(default_factory=dict)
    timed_refresh_immune_slices: list[int] = field(default_factory=list)
    cross_filters_enabled: bool = field(default=False)
    filter_scopes: SerializableOptional[dict[str, Any]] = field(default_factory=dict)
    chart_configuration: dict[str, ChartConfiguration] = object_field(cls=ChartConfiguration, dict_right=True,
                                                                      default_factory=dict)
    global_chart_configuration: GlobalChartConfiguration = object_field(cls=GlobalChartConfiguration,
                                                                        default_factory=GlobalChartConfiguration)
    default_filters: SerializableOptional[dict[str, Any]] = field(default=None)

    # List of native filters and dividers, kept as the dicts Superset stores (see native_filters).
    native_filter_configuration: SerializableOptional[list[dict[str, Any]]] = field(default=None)

    # Other keys of DashboardJSONMetadataSchema (6.1.0); absent unless read or set.
    color_namespace: SerializableOptional[str] = field(default=None)
    map_label_colors: SerializableOptional[dict[str, str]] = field(default=None)
    positions: SerializableOptional[dict[str, Any]] = field(default=None)
    filter_bar_orientation: SerializableOptional[FilterBarOrientation] = field(default=None)
    show_chart_timestamps: SerializableOptional[bool] = field(default=None)
    chart_customization_config: SerializableOptional[list[dict[str, Any]]] = field(default=None)
    stagger_refresh: SerializableOptional[bool] = field(default=None)
    stagger_time: SerializableOptional[int] = field(default=None)

    def __post_init__(self) -> None:
        super().__post_init__()
        # Ids of the native filter items created by the library: only their scopes are recomputed.
        self._library_filter_ids: set[str] = set()
        # Filter id -> chart ids in scope, for filters restricted to some charts (excluded = the others).
        self._filter_charts: dict[str, list[int]] = {}

    def clear_native_filters(self) -> None:
        self.native_filter_configuration = []
        self._library_filter_ids = set()
        self._filter_charts = {}

    def add_filter_divider(self, title: str, description: str = "",
                           id: str | None = None) -> native_filters.NativeFilterItem:
        """Section divider in the native filter bar."""
        return self._add_native_item(native_filters.divider_config(title, description, id))

    def add_native_filter(self, name: str, dataset: Any = None, column: str | None = None, parent: Any = None,
                          charts: Iterable[Any] | None = None, excluded_charts: Iterable[Any] | None = None,
                          **options: Any) -> native_filters.NativeFilterItem:
        """Native filter on `column` of `dataset` (a saved Dataset, its id or its uuid).

        Without `dataset` the filter has no target (``targets: [{}]``), e.g.
        ``add_native_filter("Period", filter_type=FilterType.TIME)``.
        `parent` is a filter (or a list of filters) returned by this method: the new filter depends on them
        (``cascadeParentIds``). The filter applies to every chart of the dashboard, or only to `charts`, or
        to all but `excluded_charts` (charts or chart ids). Other options are those of
        :func:`native_filters.filter_config`, for example ``adhoc_filters=[...]``, ``multiSelect=True`` or
        ``inverseSelection=True``.
        """
        if charts is not None and excluded_charts is not None:
            raise ValueError("pass either charts or excluded_charts, not both.")
        parents: list[native_filters.NativeFilterItem | str] = (
            list(parent) if isinstance(parent, (list, tuple)) else [parent] if parent else [])
        item = self._add_native_item(native_filters.filter_config(name, dataset, column, parents, **options))
        if charts is not None:
            self._filter_charts[item.id] = [_chart_id(chart) for chart in charts]
        elif excluded_charts is not None:
            item.config["scope"]["excluded"] = [_chart_id(chart) for chart in excluded_charts]
        return item

    def update_native_filter_scopes(self, layout: Any) -> None:
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

    def add_chart(self, chart: Any) -> None:
        chart_configuration = ChartConfiguration(id=chart.id)
        if self.global_chart_configuration.chartsInScope:
            for chart_id in self.global_chart_configuration.chartsInScope:
                if chart_id != chart.id:
                    chart_configuration.crossFilters.chartsInScope.append(chart_id)
        self.chart_configuration[str(chart.id)] = chart_configuration

        self.global_chart_configuration.chartsInScope.append(chart.id)


def _chart_id(chart: Any) -> int:
    return chart if isinstance(chart, int) else int(chart.id)


# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"GlobalChartconfiguration": "GlobalChartConfiguration",
    "GlobalChartconfigurationScope": "GlobalChartConfigurationScope"})

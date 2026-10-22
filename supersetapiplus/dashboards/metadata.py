from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.fields import default_string, object_field
from supersetapiplus.typing import SerializableOptional


@dataclass
class CrossFilters(SerializableModel):
    scope: str = 'global'
    chartsInScope: list[int] = field(default_factory=list)


@dataclass
class ChartConfiguration(SerializableModel):
    id: int | None = field(default=None)
    crossFilters: CrossFilters = object_field(cls=CrossFilters, default_factory=CrossFilters)


@dataclass
class GlobalChartconfigurationScope(SerializableModel):
    rootPath: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)


@dataclass
class GlobalChartconfiguration(SerializableModel):
    scope: GlobalChartconfigurationScope = object_field(cls=GlobalChartconfigurationScope,
                                                        default_factory=GlobalChartconfigurationScope)
    chartsInScope: list[str] = field(default_factory=list)


@dataclass
class Metadata(SerializableModel):
    JSON_FIELDS = ['default_filters']

    color_scheme: str = default_string()
    refresh_frequency: int = field(default=0)
    shared_label_colors: dict[str, str] = field(default_factory=dict)
    color_scheme_domain: list[str] = field(default_factory=list)
    expanded_slices: dict = field(default_factory=dict)
    label_colors: dict = field(default_factory=dict)
    timed_refresh_immune_slices: list[str] = field(default_factory=list)
    cross_filters_enabled: bool = field(default=False)
    filter_scopes: SerializableOptional[dict] = field(default_factory=dict)
    chart_configuration: dict[str, ChartConfiguration] = object_field(cls=ChartConfiguration, dict_right=True,
                                                                      default_factory=dict)
    global_chart_configuration: GlobalChartconfiguration = object_field(cls=GlobalChartconfiguration,
                                                                        default_factory=GlobalChartconfiguration)
    default_filters: SerializableOptional[dict] = field(default=None)

    native_filter_configuration: SerializableOptional[dict] = field(default=None)

    def add_chart(self, chart):
        chart_configuration = ChartConfiguration(id=chart.id)
        if self.global_chart_configuration.chartsInScope:
            for chart_id in self.global_chart_configuration.chartsInScope:
                if chart_id != chart.id:
                    chart_configuration.crossFilters.chartsInScope.append(chart_id)
        self.chart_configuration[str(chart.id)] = chart_configuration

        self.global_chart_configuration.chartsInScope.append(chart.id)

# supersetapiplus/charts/cal_heatmap.py

from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import (
    CalendarDomain,
    CalendarSubdomain,
    ChartType,
    DateFormatType,
    NumberFormatType,
)
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional


@dataclass
class CalHeatmapOption(Option):
    """Calendar heatmap params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    Legacy plugin: the backend (superset/viz.py CalHeatmapViz) reads domain_granularity and
    subdomain_granularity. The time column is granularity_sqla (the UI proposes the dataset's main one).
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.CAL_HEATMAP)
    # The plugin has no dimension control: groupby is absent.
    groupby: SerializableOptional[list[Any] | MissingField] = field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    granularity_sqla: SerializableOptional[str] = None
    time_range: SerializableOptional[str] = 'No filter'
    domain_granularity: CalendarDomain = field(default_factory=lambda: CalendarDomain.MONTH)
    subdomain_granularity: CalendarSubdomain = field(default_factory=lambda: CalendarSubdomain.DAY)
    # Sequential color scheme id from an extensible registry.
    linear_color_scheme: str = 'superset_seq_1'
    cell_size: int = 10
    cell_padding: int = 2
    cell_radius: int = 0
    steps: int = 10
    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    x_axis_time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    show_legend: bool = True
    show_metric_name: bool = True
    show_values: bool = False


@dataclass
class CalHeatmapFormData(CalHeatmapOption):
    """Form data for CalHeatmap; same fields as CalHeatmapOption."""
    pass


@dataclass
class CalHeatmapQueryObject(Query):
    """Query object for CalHeatmap (no additional attributes needed)."""
    pass


@dataclass
class CalHeatmapQueryContext(QueryContext):
    """
    Query context for CalHeatmap, containing:
      - queries: list of CalHeatmapQueryObject
      - form_data: CalHeatmapFormData
    """
    queries: list[CalHeatmapQueryObject] = object_field(
        cls=CalHeatmapQueryObject, default_factory=list
    )
    form_data: CalHeatmapFormData = object_field(
        cls=CalHeatmapFormData, default_factory=CalHeatmapFormData
    )

    def _default_query_object_class(self) -> type[Query]:
        return CalHeatmapQueryObject


@dataclass
class CalHeatmapChart(Chart):
    """
    Chart class for CalHeatmap. Combines:
      - params: CalHeatmapOption
      - query_context: CalHeatmapQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.CAL_HEATMAP
    viz_type: ChartType = field(default_factory=lambda: ChartType.CAL_HEATMAP)
    params: CalHeatmapOption = object_field(
        cls=CalHeatmapOption, default_factory=CalHeatmapOption
    )
    query_context: CalHeatmapQueryContext = object_field(
        cls=CalHeatmapQueryContext, default_factory=CalHeatmapQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return CalHeatmapOption

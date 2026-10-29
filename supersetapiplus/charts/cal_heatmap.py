
# supersetapiplus/charts/cal_heatmap.py
from typing import Any, ClassVar

from pydantic import Field

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
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional


class CalHeatmapOption(Option):
    """Calendar heatmap params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    Legacy plugin: the backend (superset/viz.py CalHeatmapViz) reads domain_granularity and
    subdomain_granularity. The time column is granularity_sqla (the UI proposes the dataset's main one).

    The chart renders through /superset/explore_json (useLegacyApi). Its query_context is the one Explore saves (the
    default buildQuery), but Superset 6.1.0 answers it on /api/v1/chart/data with one aggregate row, not the calendar:
    ``client.charts.get_chart_data()`` (which warns), reports and alerts do not reproduce what the chart shows.
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.CAL_HEATMAP)
    # The plugin has no dimension control: groupby is absent.
    groupby: SerializableOptional[list[Any] | MissingField] = Field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    granularity_sqla: SerializableOptional[str] = None
    time_range: SerializableOptional[str] = 'No filter'
    domain_granularity: CalendarDomain = Field(default_factory=lambda: CalendarDomain.MONTH)
    subdomain_granularity: CalendarSubdomain = Field(default_factory=lambda: CalendarSubdomain.DAY)
    # Sequential color scheme id from an extensible registry.
    linear_color_scheme: str = 'superset_seq_1'
    cell_size: int = 10
    cell_padding: int = 2
    cell_radius: int = 0
    steps: int = 10
    y_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    x_axis_time_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)
    show_legend: bool = True
    show_metric_name: bool = True
    show_values: bool = False


class CalHeatmapFormData(CalHeatmapOption):
    """Form data for CalHeatmap; same fields as CalHeatmapOption."""
    pass


class CalHeatmapQueryObject(Query):
    """Query object for CalHeatmap (no additional attributes needed)."""
    pass


class CalHeatmapQueryContext(QueryContext):
    """
    Query context for CalHeatmap, containing:
      - queries: list of CalHeatmapQueryObject
      - form_data: CalHeatmapFormData
    """
    queries: list[CalHeatmapQueryObject] = Field(default_factory=list)
    form_data: CalHeatmapFormData = Field(default_factory=CalHeatmapFormData)

    def _default_query_object_class(self) -> type[Query]:
        return CalHeatmapQueryObject


class CalHeatmapChart(Chart):
    """
    Chart class for CalHeatmap. Combines:
      - params: CalHeatmapOption
      - query_context: CalHeatmapQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.CAL_HEATMAP
    viz_type: ChartType = Field(default_factory=lambda: ChartType.CAL_HEATMAP)
    params: CalHeatmapOption = Field(default_factory=CalHeatmapOption)
    query_context: CalHeatmapQueryContext = Field(default_factory=CalHeatmapQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return CalHeatmapOption

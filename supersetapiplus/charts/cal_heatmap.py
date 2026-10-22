# supersetapiplus/charts/cal_heatmap.py

from dataclasses import dataclass, field
from typing import List, Type

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType


@dataclass
class CalHeatmapOption(Option):
    """
    Configuration options for CalHeatmap (calendar heatmap).

    Fields kept or added:
      - datasource_id: numeric ID of the data source
      - datasource_type: type of the data source (e.g., "table")
      - groupby: list of fields to group by
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.CAL_HEATMAP)
    groupby: List[str] = field(default_factory=list)


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
    queries: List[CalHeatmapQueryObject] = object_field(
        cls=CalHeatmapQueryObject, default_factory=list
    )
    form_data: CalHeatmapFormData = object_field(
        cls=CalHeatmapFormData, default_factory=CalHeatmapFormData
    )

    def _default_query_object_class(self) -> Type[Query]:
        return CalHeatmapQueryObject


@dataclass
class CalHeatmapChart(Chart):
    """
    Chart class for CalHeatmap. Combines:
      - params: CalHeatmapOption
      - query_context: CalHeatmapQueryContext
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.CAL_HEATMAP)
    params: CalHeatmapOption = object_field(
        cls=CalHeatmapOption, default_factory=CalHeatmapOption
    )
    query_context: CalHeatmapQueryContext = object_field(
        cls=CalHeatmapQueryContext, default_factory=CalHeatmapQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> Type[Option]:
        return CalHeatmapOption

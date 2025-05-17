# supersetapiplus/charts/box_plot.py

from dataclasses import dataclass, field
from typing import List, Type

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType


@dataclass
class BoxPlotOption(Option):
    """
    Configuration options for a Box Plot chart.

    Only fields expected to remain after the diff:
      - datasource_id: the numeric ID of the data source
      - datasource_type: the type of the data source (e.g. "table")
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BOX_PLOT)


@dataclass
class BoxPlotFormData(BoxPlotOption):
    """Form data for Box Plot; inherits same fields as BoxPlotOption."""
    pass


@dataclass
class BoxPlotQueryObject(Query):
    """Query object for Box Plot (no extra attributes required)."""
    pass


@dataclass
class BoxPlotQueryContext(QueryContext):
    """
    Query context for Box Plot, holding:
      - a list of BoxPlotQueryObject
      - the associated form_data
    """
    queries: List[BoxPlotQueryObject] = object_field(
        cls=BoxPlotQueryObject, default_factory=list
    )
    form_data: BoxPlotFormData = object_field(
        cls=BoxPlotFormData, default_factory=BoxPlotFormData
    )

    def _default_query_object_class(self) -> Type[Query]:
        return BoxPlotQueryObject


@dataclass
class BoxPlotChart(Chart):
    """
    Chart class for Box Plot. Ties together:
      - params: BoxPlotOption
      - query_context: BoxPlotQueryContext
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BOX_PLOT)
    params: BoxPlotOption = object_field(
        cls=BoxPlotOption, default_factory=BoxPlotOption
    )
    query_context: BoxPlotQueryContext = object_field(
        cls=BoxPlotQueryContext, default_factory=BoxPlotQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> Type[Option]:
        return BoxPlotOption

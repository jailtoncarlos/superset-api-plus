# supersetapiplus/charts/big_number_total.py

from dataclasses import dataclass, field
from typing import List, Type

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType


@dataclass
class BigNumberTotalOption(Option):
    """
    Configuration options for Big Number Total chart.

    Fields retained or added after diff:
      - datasource_id: numeric data source ID
      - datasource_type: data source type
      - groupby: list of grouping fields
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER_TOTAL)


@dataclass
class BigNumberTotalFormData(BigNumberTotalOption):
    """Form data for Big Number Total; same fields as BigNumberTotalOption."""
    pass


@dataclass
class BigNumberTotalQueryObject(Query):
    """Query object for Big Number Total (no additional attributes)."""
    pass


@dataclass
class BigNumberTotalQueryContext(QueryContext):
    """
    Query context for Big Number Total:
      - queries: list of BigNumberTotalQueryObject
      - form_data: BigNumberTotalFormData
    """
    queries: List[BigNumberTotalQueryObject] = object_field(
        cls=BigNumberTotalQueryObject, default_factory=list
    )
    form_data: BigNumberTotalFormData = object_field(
        cls=BigNumberTotalFormData, default_factory=BigNumberTotalFormData
    )

    def _default_query_object_class(self) -> Type[Query]:
        return BigNumberTotalQueryObject


@dataclass
class BigNumberTotalChart(Chart):
    """
    Chart class for Big Number Total. Encapsulates:
      - params: BigNumberTotalOption
      - query_context: BigNumberTotalQueryContext
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER_TOTAL)
    params: BigNumberTotalOption = object_field(
        cls=BigNumberTotalOption, default_factory=BigNumberTotalOption
    )
    query_context: BigNumberTotalQueryContext = object_field(
        cls=BigNumberTotalQueryContext, default_factory=BigNumberTotalQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> Type[Option]:
        return BigNumberTotalOption

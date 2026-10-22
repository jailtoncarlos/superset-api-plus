# supersetapiplus/charts/mixed_timeseries.py

from dataclasses import dataclass, field
from typing import List, Type

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType


@dataclass
class MixedTimeseriesOption(Option):
    """
    Configuration options for Mixed Time Series chart.

    Fields retained or added after diff:
      - datasource_id: numeric ID of data source
      - datasource_type: type of data source
      - groupby: list of grouping fields
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.MIXED_TIMESERIES)


@dataclass
class MixedTimeseriesFormData(MixedTimeseriesOption):
    """Form data for Mixed Time Series; same fields as MixedTimeseriesOption."""
    pass


@dataclass
class MixedTimeseriesQueryObject(Query):
    """Query object for Mixed Time Series (no additional attributes)."""
    pass


@dataclass
class MixedTimeseriesQueryContext(QueryContext):
    """
    Query context for Mixed Time Series:
      - queries: list of MixedTimeseriesQueryObject
      - form_data: MixedTimeseriesFormData
    """
    queries: List[MixedTimeseriesQueryObject] = object_field(
        cls=MixedTimeseriesQueryObject, default_factory=list
    )
    form_data: MixedTimeseriesFormData = object_field(
        cls=MixedTimeseriesFormData, default_factory=MixedTimeseriesFormData
    )

    def _default_query_object_class(self) -> Type[Query]:
        return MixedTimeseriesQueryObject


@dataclass
class MixedTimeseriesChart(Chart):
    """
    Chart class for Mixed Time Series. Bundles:
      - params: MixedTimeseriesOption
      - query_context: MixedTimeseriesQueryContext
    """
    # O Superset pode gravar query_context.form_data sem as chaves da query B (metrics_b, groupby_b...).
    PARAMS_ONLY_FIELD_SUFFIXES = ('_b',)

    viz_type: ChartType = field(default_factory=lambda: ChartType.MIXED_TIMESERIES)
    params: MixedTimeseriesOption = object_field(
        cls=MixedTimeseriesOption, default_factory=MixedTimeseriesOption
    )
    query_context: MixedTimeseriesQueryContext = object_field(
        cls=MixedTimeseriesQueryContext, default_factory=MixedTimeseriesQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> Type[Option]:
        return MixedTimeseriesOption

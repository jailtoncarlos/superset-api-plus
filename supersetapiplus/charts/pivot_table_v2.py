"""Charts."""
from dataclasses import dataclass, field
from typing import List

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import OrderByTyping
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn, CurrencyFormat
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.table import TableOptionBase
from supersetapiplus.charts.types import ChartType, MetricsLayoutEnum, MetricType, OrderType, NumberFormatType, \
    DateFormatType
from supersetapiplus.typing import SerializableOptional


@dataclass
class PivotTableV2Option(TableOptionBase):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)

    groupby: SerializableOptional[List[OrderByTyping]] = None

    groupbyColumns: List[QueryFormColumn] = object_field(default_factory=list)
    groupbyRows: List[QueryFormColumn] = object_field(default_factory=list)

    metricsLayout: MetricsLayoutEnum = field(default_factory=lambda: MetricsLayoutEnum.COLUMNS)
    combineMetric: bool = False,

    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=dict)
    valueFormat: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    date_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    series_limit: SerializableOptional[int] = 0
    colOrder:  OrderType = field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    rowOrder: OrderType = field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    aggregateFunction: MetricType = field(default_factory=lambda: MetricType.SUM)
    transposePivot: SerializableOptional[bool] = field(default=None)

    rowTotals: SerializableOptional[bool] = False
    rowSubTotals: SerializableOptional[bool] = False
    rowSubtotalPosition: SerializableOptional[bool] = False
    colTotals: SerializableOptional[bool] = False
    colSubTotals: SerializableOptional[bool] = False
    colSubtotalPosition: SerializableOptional[bool] = field(default=None)

    # currencyFormat,
    # emitCrossFilters,
    # setDataMask,
    # selectedFilters,
    # verboseMap,
    # columnFormats,
    # currencyFormats,
    # metricColorFormatters,
    # dateFormatters,
    # onContextMenu,
    # timeGrainSqla,

    def __post_init__(self):
        super().__post_init__()
        self.groupby = None


@dataclass()
class PivotTableV2FormData(PivotTableV2Option):
    ...


@dataclass
class PivotTableV2QueryObject(Query):
    ...


@dataclass
class PivotTableV2QueryContext(QueryContext):
    queries: List[PivotTableV2QueryObject] = object_field(cls=PivotTableV2QueryObject, default_factory=list)
    form_data: PivotTableV2FormData = object_field(cls=PivotTableV2FormData, default_factory=PivotTableV2FormData)

    def _default_query_object_class(self) -> type[Query]:
        return PivotTableV2QueryObject


@dataclass
class PivotTableV2Chart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIVOT_TALBE_V2)
    params: PivotTableV2Option = object_field(cls=PivotTableV2Option, default_factory=PivotTableV2Option)
    query_context: PivotTableV2QueryContext = object_field(cls=PivotTableV2QueryContext,
                                                           default_factory=PivotTableV2QueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PivotTableV2Option
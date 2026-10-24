"""Charts."""
from dataclasses import dataclass, field
from typing import ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import OrderByTyping
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.table import TableOptionBase
from supersetapiplus.charts.types import (
    ChartType,
    DateFormatType,
    MetricsLayoutEnum,
    NumberFormatType,
    OrderType,
    PivotAggregateFunction,
    TimeGrain,
)
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.typing import SerializableOptional


@dataclass
class PivotTableV2Option(TableOptionBase):
    # The pivot has no groupby control: its dimensions are groupbyRows/groupbyColumns, both optional.
    _require_groupby: ClassVar[bool] = False
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIVOT_TABLE_V2)

    groupby: SerializableOptional[list[OrderByTyping]] = None

    groupbyColumns: list[QueryFormColumn] = object_field(default_factory=list)
    groupbyRows: list[QueryFormColumn] = object_field(default_factory=list)

    metricsLayout: MetricsLayoutEnum = field(default_factory=lambda: MetricsLayoutEnum.COLUMNS)
    combineMetric: bool = False

    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    valueFormat: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    date_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    series_limit: SerializableOptional[int] = None
    row_limit: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    colOrder:  OrderType = field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    rowOrder: OrderType = field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    aggregateFunction: PivotAggregateFunction = field(default_factory=lambda: PivotAggregateFunction.SUM)
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

    def _editable_groupby(self) -> list:
        # The pivot buildQuery reads only groupbyColumns/groupbyRows: dimensions added in code are rows,
        # as the "Rows" control in Explore.
        if not isinstance(self.groupbyRows, list):
            self.groupbyRows = []
        return self.groupbyRows


@dataclass()
class PivotTableV2FormData(PivotTableV2Option):
    ...


@dataclass
class PivotTableV2QueryObject(Query):
    ...


@dataclass
class PivotTableV2QueryContext(QueryContext):
    queries: list[PivotTableV2QueryObject] = object_field(cls=PivotTableV2QueryObject, default_factory=list)
    form_data: PivotTableV2FormData = object_field(cls=PivotTableV2FormData, default_factory=PivotTableV2FormData)

    def _default_query_object_class(self) -> type[Query]:
        return PivotTableV2QueryObject


@dataclass
class PivotTableV2Chart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.PIVOT_TABLE_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIVOT_TABLE_V2)
    params: PivotTableV2Option = object_field(cls=PivotTableV2Option, default_factory=PivotTableV2Option)
    query_context: PivotTableV2QueryContext = object_field(cls=PivotTableV2QueryContext,
                                                           default_factory=PivotTableV2QueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PivotTableV2Option

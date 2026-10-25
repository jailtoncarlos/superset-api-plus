"""Charts."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
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
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional


class PivotTableV2Option(TableOptionBase):
    # The pivot has no groupby control: its dimensions are groupbyRows/groupbyColumns, both optional.
    _require_groupby: ClassVar[bool] = False
    viz_type: ChartType = Field(default_factory=lambda: ChartType.PIVOT_TABLE_V2)

    groupby: SerializableOptional[list[Any] | MissingField] = None

    groupbyColumns: list[QueryFormColumn] = Field(default_factory=list)
    groupbyRows: list[QueryFormColumn] = Field(default_factory=list)

    metricsLayout: MetricsLayoutEnum = Field(default_factory=lambda: MetricsLayoutEnum.COLUMNS)
    combineMetric: bool = False

    currency_format: SerializableOptional[CurrencyFormat] = None
    valueFormat: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    date_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)

    series_limit: SerializableOptional[int] = None
    row_limit: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)
    colOrder:  OrderType = Field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    rowOrder: OrderType = Field(default_factory=lambda: OrderType.KEY_A_TO_Z)
    aggregateFunction: PivotAggregateFunction = Field(default_factory=lambda: PivotAggregateFunction.SUM)
    transposePivot: SerializableOptional[bool] = None

    rowTotals: SerializableOptional[bool] = False
    rowSubTotals: SerializableOptional[bool] = False
    rowSubtotalPosition: SerializableOptional[bool] = False
    colTotals: SerializableOptional[bool] = False
    colSubTotals: SerializableOptional[bool] = False
    colSubtotalPosition: SerializableOptional[bool] = None

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

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        self.groupby = None

    def _editable_groupby(self) -> list[Any]:
        # The pivot buildQuery reads only groupbyColumns/groupbyRows: dimensions added in code are rows,
        # as the "Rows" control in Explore.
        if not isinstance(self.groupbyRows, list):
            self.groupbyRows = []
        return self.groupbyRows


class PivotTableV2FormData(PivotTableV2Option):
    ...


class PivotTableV2QueryObject(Query):
    ...


class PivotTableV2QueryContext(QueryContext):
    queries: list[PivotTableV2QueryObject] = Field(default_factory=list)
    form_data: PivotTableV2FormData = Field(default_factory=PivotTableV2FormData)

    def _default_query_object_class(self) -> type[Query]:
        return PivotTableV2QueryObject


@dataclass
class PivotTableV2Chart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.PIVOT_TABLE_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIVOT_TABLE_V2)
    params: PivotTableV2Option = field(default_factory=PivotTableV2Option)
    query_context: PivotTableV2QueryContext = field(default_factory=PivotTableV2QueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PivotTableV2Option

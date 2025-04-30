import logging
from dataclasses import dataclass, field
from typing import List, Union, Dict, Protocol, runtime_checkable

from supersetapiplus.base.base import Object, object_field
from supersetapiplus.charts.metric import AdhocMetricColumn, MetricHelper, Metric, OrderByTyping, MetricsListMixin, \
    AdhocMetric
from supersetapiplus.charts.types import FilterOperatorType, TimeGrain, FilterExpressionType, HorizontalAlignType, \
    NumberFormatType, CurrentPositionType, CurrencyCodeType, MetricType, \
    ColumnType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import FilterValues, Optional

logger = logging.getLogger(__name__)

@dataclass
class CurrencyFormat(Object):
    symbolPosition: CurrentPositionType = None
    symbol: CurrencyCodeType = None


@dataclass
class ColumnConfig(Object):
    horizontalAlign: HorizontalAlignType = field(default_factory=lambda: HorizontalAlignType.LEFT)
    d3NumberFormat: Optional[NumberFormatType] = field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)
    d3SmallNumberFormat: Optional[NumberFormatType] = field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)

    alignPositiveNegative: Optional[bool] = None
    colorPositiveNegative: Optional[bool] = None
    showCellBars: Optional[bool] = None
    columnWidth: Optional[int] = None
    currency_format: Optional[CurrencyFormat] = object_field(cls=CurrencyFormat, default_factory=CurrencyFormat)


@dataclass
class QuerieExtra(Object):
    time_grain_sqla: Optional[TimeGrain] = None
    having: str = ''
    where: str = ''


@dataclass
class AdhocColumn(Object):
    hasCustomLabel: Optional[bool]
    label: str
    sqlExpression: str
    timeGrain: Optional[str]
    columnType: Optional[ColumnType]


Column = Union[AdhocColumn, str]


@dataclass
class QueryFilterClause(Object):
    col: Column
    val: Optional[FilterValues]
    op: FilterOperatorType = field(default_factory=lambda: FilterOperatorType.EQUALS)


@runtime_checkable
class SupportsColumns(Protocol):
    # This is a protocol that defines the expected structure of classes that have metric.
    columns: Optional[List[Metric]]


class ColumnsMixin:
    def _add_simple_columns(self: SupportsColumns, column_name:str):
        self.columns.append(column_name)

    def _add_custom_columns(self: SupportsColumns, label: str,
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.columns.append(metric)
        if column:
            column.expressionType = FilterExpressionType.CUSTOM_SQL


@runtime_checkable
class SupportsOrderby(Protocol):
    # This is a protocol that defines the expected structure of classes that have metric.
    orderby: Optional[List[OrderByTyping]]


class OrderByMixin:
    def _add_simple_orderby(self, column_name: str,
                            sort_ascending: bool):
        self.orderby.append((column_name, sort_ascending))

    def _add_custom_orderby(self, label: str,
                            sort_ascending: bool,
                            column: AdhocMetricColumn,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.orderby.append((metric, sort_ascending))


@dataclass
class QueryObject(Object, MetricsListMixin, ColumnsMixin, OrderByMixin):
    row_limit: Optional[int] = 100
    series_limit: Optional[int] = 0
    series_limit_metric: Optional[Metric] = object_field(cls=AdhocMetric, default_factory=AdhocMetric)
    order_desc: bool = True
    orderby: Optional[List[OrderByTyping]] = object_field(cls=AdhocMetric, default_factory=list)

    filters: List[QueryFilterClause] = object_field(cls=QueryFilterClause, default_factory=list)
    extras: QuerieExtra = object_field(cls=QuerieExtra, default_factory=QuerieExtra)
    columns: Optional[List[Metric]] = object_field(cls=AdhocMetric, default_factory=list)
    metrics: Optional[List[Metric]] = object_field(cls=AdhocMetric, default_factory=list)

    applied_time_extras: Dict = field(default_factory=dict)
    url_params: Dict = field(default_factory=dict)
    custom_params: Dict = field(default_factory=dict)
    custom_form_data: Dict = field(default_factory=dict)
    annotation_layers: List = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        if not self.metrics:
            self.metrics:List[Metric] = []
        if not self.orderby:
            self.orderby:List[OrderByTyping] = []
        if not self.columns:
            self.columns:List[Metric] = []
        if not self.row_limit == 0:
            self.row_limit = 100

    def validate(self, data: dict):
        super().validate(data)

        if not self.orderby:
            raise ValidationError(message='Field orderby cannot be empty.',
                                  solution='Set the "automatic_order=OrderBy(automate=True)" argument in the add_simple_metric or add_custom_metric methods. If you want to customize a different order, use the add_simple_orderby or add_custom_orderby methods.')
        if not self.metrics:
            raise ValidationError(message='Field metrics cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')
    def _add_simple_filter(self, column_name: Column,
                           value: FilterValues,
                           operator: FilterOperatorType = FilterOperatorType.EQUALS) -> None:
        query_filter_clause = QueryFilterClause(col=column_name, val=value, op=operator)
        self.filters.append(query_filter_clause)

    def _add_extra_where(self, sql: str):
        if self.extras.where:
            self.extras.where = f'{self.extras.where} AND '
        self.extras.where = self.extras.where + f'({sql})'

    def _add_extra_having(self, sql: str):
        raise NotImplementedError



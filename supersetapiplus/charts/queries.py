import logging
from dataclasses import dataclass, field
from typing import List, Union, Dict, Protocol, runtime_checkable

from supersetapiplus.base.base import SerializableModel, object_field
from supersetapiplus.charts.metric import AdhocMetricColumn, MetricHelper, Metric, OrderByTyping, MetricsListMixin, \
    AdhocMetric
from supersetapiplus.charts.types import FilterOperatorType, TimeGrain, FilterExpressionType, HorizontalAlignType, \
    NumberFormatType, CurrentPositionType, CurrencyCodeType, MetricType, \
    ColumnType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import FilterValues, SerializableOptional

logger = logging.getLogger(__name__)

@dataclass
class CurrencyFormat(SerializableModel):
    symbolPosition: CurrentPositionType = None
    symbol: CurrencyCodeType = None


@dataclass
class ColumnConfig(SerializableModel):
    horizontalAlign: HorizontalAlignType = field(default_factory=lambda: HorizontalAlignType.LEFT)
    d3NumberFormat: SerializableOptional[NumberFormatType] = field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)
    d3SmallNumberFormat: SerializableOptional[NumberFormatType] = field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)

    alignPositiveNegative: SerializableOptional[bool] = None
    colorPositiveNegative: SerializableOptional[bool] = None
    showCellBars: SerializableOptional[bool] = None
    columnWidth: SerializableOptional[int] = None
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default_factory=CurrencyFormat)


@dataclass
class QuerieExtra(SerializableModel):
    time_grain_sqla: SerializableOptional[TimeGrain] = None
    having: str = ''
    where: str = ''


@dataclass
class AdhocColumn(SerializableModel):
    hasCustomLabel: SerializableOptional[bool]
    label: str
    sqlExpression: str
    timeGrain: SerializableOptional[str]
    columnType: SerializableOptional[ColumnType]


Column = Union[AdhocColumn, str]


@dataclass
class QueryFilterClause(SerializableModel):
    col: Column
    val: SerializableOptional[FilterValues]
    op: FilterOperatorType = field(default_factory=lambda: FilterOperatorType.EQUALS)


@runtime_checkable
class SupportsColumns(Protocol):
    # This is a protocol that defines the expected structure of classes that have metric.
    columns: SerializableOptional[List[Metric]]


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
    orderby: SerializableOptional[List[OrderByTyping]]


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
class QuerySerializableModel(SerializableModel, MetricsListMixin, ColumnsMixin, OrderByMixin):
    row_limit: SerializableOptional[int] = 100
    series_limit: SerializableOptional[int] = 0
    series_limit_metric: SerializableOptional[Metric] = object_field(cls=AdhocMetric, default_factory=AdhocMetric)
    order_desc: bool = True
    orderby: SerializableOptional[List[OrderByTyping]] = object_field(cls=AdhocMetric, default_factory=list)

    filters: List[QueryFilterClause] = object_field(cls=QueryFilterClause, default_factory=list)
    extras: QuerieExtra = object_field(cls=QuerieExtra, default_factory=QuerieExtra)
    columns: SerializableOptional[List[Metric]] = object_field(cls=AdhocMetric, default_factory=list)
    metrics: SerializableOptional[List[Metric]] = object_field(cls=AdhocMetric, default_factory=list)

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



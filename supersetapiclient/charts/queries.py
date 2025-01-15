import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Union, Literal, get_args, Dict

from supersetapiclient.base.base import Object, ObjectField, default_string
from supersetapiclient.charts.filters import AdhocFilterClause
from supersetapiclient.charts.types import FilterOperatorType, TimeGrain, FilterExpressionType, SqlMapType, \
    GenericDataType, HorizontalAlignType, NumberFormatType, CurrentPositionType, CurrencyCodeType, MetricType, \
    FilterClausesType, ColumnType
from supersetapiclient.exceptions import ValidationError
from supersetapiclient.typing import FilterValues, Optional

logger = logging.getLogger(__name__)

@dataclass
class CurrencyFormat(Object):
    symbolPosition: CurrentPositionType = None
    symbol: CurrencyCodeType = None


@dataclass
class ColumnConfig(Object):
    horizontalAlign: HorizontalAlignType = HorizontalAlignType.LEFT
    d3NumberFormat: Optional[NumberFormatType] = NumberFormatType.ORIGINAL_VALUE
    d3SmallNumberFormat: Optional[NumberFormatType] = NumberFormatType.ORIGINAL_VALUE
    alignPositiveNegative: Optional[bool] = None
    colorPositiveNegative: Optional[bool] = None
    showCellBars: Optional[bool] = None
    columnWidth: Optional[int] = None
    currency_format: Optional[CurrencyFormat] = ObjectField(cls=CurrencyFormat, default_factory=CurrencyFormat)


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
    op: FilterOperatorType = FilterOperatorType.EQUALS


@dataclass
class AdhocMetricColumn(Object):
    column_name: str = default_string()
    id: Optional[int] = None
    verbose_name: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None
    filterable: bool = True
    groupby: bool = True
    is_dttm: bool = False
    python_date_format: Optional[str] = None
    type: SqlMapType = None
    type_generic: Optional[GenericDataType] = None

    def validate(self, data: dict):
        if not self.column_name or self.type:
            raise ValidationError(message='At least the column_name and type fields must be informed.',
                                  solution='')

    def is_empty(self):
        if self.id is None \
            and self.verbose_name is None\
            and self.description is None\
            and self.expression is None\
            and self.python_date_format is None\
            and self.type is None\
            and self.type_generic is None:
            return True
        else:
            return False


@dataclass
class AdhocMetric(Object):
    sqlExpression: Optional[str]
    aggregate: Optional[MetricType]
    timeGrain: Optional[str]
    columnType: Optional[ColumnType]
    label: Optional[str] = default_string()
    expressionType: FilterExpressionType = FilterExpressionType.CUSTOM_SQL
    hasCustomLabel: Optional[bool] = False
    column: Optional[AdhocMetricColumn] = ObjectField(cls=AdhocMetricColumn, default_factory=AdhocMetricColumn)

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.column, AdhocMetricColumn) and self.column.is_empty():
            self.column: Optional[AdhocMetricColumn] = None


Metric = Union[AdhocMetric, Literal['count', 'sum', 'avg', 'min', 'max', 'count distinct']]
OrderByTyping = tuple[Metric, bool]

class OrderBy:
    def __init__(self, automate:bool=True, sort_ascending: bool = True):
        self._automate = automate
        self._sort_ascending = sort_ascending

    def __str__(self):
        return f'automate: {self._automate}, sort_ascending: {self._sort_ascending}'

    @property
    def automate(self):
        self._automate

    @property
    def sort_ascending(self):
        self._sort_ascending


class MetricHelper:
    @classmethod
    def get_metric(cls, label: str,
                   column: AdhocMetricColumn = None,
                   sql_expression: str = None,
                   aggregate: MetricType = MetricType.COUNT):
        expression_type = FilterExpressionType.SIMPLE
        if sql_expression:
            expression_type = FilterExpressionType.CUSTOM_SQL

        if aggregate:
            cls.check_aggregate(aggregate)
            aggregate = str(aggregate).upper()

        has_custom_label = False
        if label:
            has_custom_label = True

        _metric = {
            "expressionType": str(expression_type),
            "hasCustomLabel": has_custom_label,
            'column': column,
            'sqlExpression': sql_expression,
            'aggregate': aggregate
        }
        if has_custom_label:
            _metric['label'] = label

        return AdhocMetric(**_metric)

    @classmethod
    def check_metric(cls, value):
        simple_metrics = get_args(get_args(Metric)[-1])
        if str(value) not in simple_metrics:
            raise ValidationError(message='Metric not found.',
                                  solution=f'Use one of the options:{simple_metrics}')

    @classmethod
    def check_aggregate(cls, value):
        list_aggregates = [e.value for e in MetricType]
        if str(value) not in list_aggregates:
            raise ValidationError(message='Aggregate not found.',
                                  solution=f'Use o enum types.MetricType')


class MetricsMixin:
    def _add_simple_metric(self, metric:str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metrics.append(metric)

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.metrics.append(metric)


class MetricMixin:
    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metric = metric
        if automatic_order and automatic_order.automate:
            self.sort_by_metric = True

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        if not aggregate:
            raise ValidationError(message='Argument aggregate cannot be empty.')
        if automatic_order and automatic_order.automate:
            self.sort_by_metric = True
        self.metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)


class ColumnsMixin:
    def _add_simple_columns(self, column_name:str):
        self.columns.append(column_name)

    def _add_custom_columns(self, label: str,
                           column: AdhocMetricColumn = None,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.columns.append(metric)
        if column:
            column.expressionType = FilterExpressionType.CUSTOM_SQL


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
class QueryObject(Object, MetricsMixin, ColumnsMixin, OrderByMixin):
    row_limit: Optional[int] = 100
    series_limit: Optional[int] = 0
    series_limit_metric: Optional[Metric] = ObjectField(cls=AdhocMetric, default_factory=AdhocMetric)
    order_desc: bool = True
    orderby: Optional[List[OrderByTyping]] = ObjectField(cls=AdhocMetric, default_factory=list)

    filters: List[QueryFilterClause] = ObjectField(cls=QueryFilterClause, default_factory=list)
    extras: QuerieExtra = ObjectField(cls=QuerieExtra, default_factory=QuerieExtra)
    columns: Optional[List[Metric]] =  ObjectField(cls=AdhocMetric, default_factory=list)
    metrics: Optional[List[Metric]] =  ObjectField(cls=AdhocMetric, default_factory=list)

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



import logging
from dataclasses import dataclass, field
from typing import Union, Literal, get_args, Protocol, runtime_checkable, List

from supersetapiplus.base.base import Object, default_string, object_field
from supersetapiplus.charts.types import FilterExpressionType, SqlMapType, \
    GenericDataType, MetricType, \
    ColumnType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableOptional

logger = logging.getLogger(__name__)


@dataclass
class AdhocMetricColumn(Object):
    column_name: str = default_string()
    id: SerializableOptional[int] = None
    verbose_name: SerializableOptional[str] = None
    description: SerializableOptional[str] = None
    expression: SerializableOptional[str] = None
    filterable: bool = True
    groupby: bool = True
    is_dttm: bool = False
    python_date_format: SerializableOptional[str] = None
    type: SerializableOptional[SqlMapType] = None
    type_generic: SerializableOptional[GenericDataType] = None

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
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.CUSTOM_SQL)
    column: SerializableOptional[AdhocMetricColumn] = object_field(cls=AdhocMetricColumn, default_factory=AdhocMetricColumn)
    label: SerializableOptional[str] = default_string()
    hasCustomLabel: SerializableOptional[bool] = False
    sqlExpression: SerializableOptional[str] = None
    aggregate: SerializableOptional[MetricType] = None
    timeGrain: SerializableOptional[str] = None
    columnType: SerializableOptional[ColumnType] = None

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.column, AdhocMetricColumn) and self.column.is_empty():
            self.column: SerializableOptional[AdhocMetricColumn] = None


Metric = Union[AdhocMetric, Literal['count', 'sum', 'avg', 'min', 'max', 'count distinct']]
OrderByTyping = tuple[Metric, bool]


class OrderBy:
    def __init__(self, automate: bool = True, sort_ascending: bool = True):
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


@runtime_checkable
class SupportsMetrics(Protocol):
    # This is a protocol that defines the expected structure of classes that have metrics.
    metrics: List[Metric]


class MetricsListMixin:
    def _add_simple_metric(self: SupportsMetrics, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metrics.append(metric)

    def _add_custom_metric(self: SupportsMetrics,
                           label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.metrics.append(metric)


@runtime_checkable
class SupportsMetric(Protocol):
    # This is a protocol that defines the expected structure of classes that have metric.
    metric: Metric


class SingleMetricMixin:
    def _add_simple_metric(self: SupportsMetric, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metric = metric
        if automatic_order and automatic_order.automate:
            self.sort_by_metric = True

    def _add_custom_metric(self: SupportsMetric, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        if not aggregate:
            raise ValidationError(message='Argument aggregate cannot be empty.')
        if automatic_order and automatic_order.automate:
            self.sort_by_metric = True
        self.metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)

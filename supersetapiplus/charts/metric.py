import logging
from dataclasses import dataclass, field
from typing import Union, Literal, get_args, List, Optional

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.fields import default_string, object_field
from supersetapiplus.charts.types import FilterExpressionType, SqlMapType, \
    GenericDataType, MetricType, \
    ColumnType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableOptional

logger = logging.getLogger(__name__)


@dataclass
class AdhocMetricColumn(SerializableModel):
    column_name: str = default_string()
    id: Optional[int] = field(default=None)
    verbose_name: str = field(default=None)
    description: str = field(default=None)
    expression: str = field(default=None)
    filterable: bool = True
    groupby: bool = True
    is_dttm: bool = False
    python_date_format: str = field(default=None)
    type: SerializableOptional[SqlMapType] = field(default=None)
    type_generic: SerializableOptional[GenericDataType] = field(default=None)

    # Novos campos conforme o JSON da API
    advanced_data_type: str = field(default=None)
    is_certified: bool = False
    certification_details: str = field(default=None)
    certified_by: str = field(default=None)
    warning_markdown: str = field(default=None)

    def validate(self):
        super().validate()
        if not self.column_name or not self.type:
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
class AdhocMetric(SerializableModel):
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.CUSTOM_SQL)
    sqlExpression: str = field(default=None)
    label: SerializableOptional[str] = default_string()
    hasCustomLabel: SerializableOptional[bool] = field(default=None)
    column: AdhocMetricColumn = object_field(cls=AdhocMetricColumn, default=None)
    aggregate: MetricType = field(default=None)

    timeGrain: SerializableOptional[str] = field(default=None)
    columnType: SerializableOptional[ColumnType] = field(default=None)

    # Novos campos
    optionName: SerializableOptional[str] = field(default=None)
    datasourceWarning: SerializableOptional[bool] = field(default=None)

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


@dataclass
class MetricsListMixin:
    metrics: List[Metric] = object_field(cls=AdhocMetric, default_factory=list)

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metrics.append(metric)

    def _add_custom_metric(self,
                           label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.metrics.append(metric)


@dataclass
class SingleMetricMixin:
    metric: Metric = object_field(cls=AdhocMetric, default=None)
    sort_by_metric: bool = False

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

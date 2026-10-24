import logging
from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.fields import default_string, object_field
from supersetapiplus.charts.types import (
    ColumnType,
    FilterExpressionType,
    GenericDataType,
    MetricType,
    TimeGrain,
)
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional

logger = logging.getLogger(__name__)


@dataclass
class AdhocMetricColumn(SerializableModel):
    column_name: str = default_string()
    id: int | None = field(default=None)
    verbose_name: str = field(default=None)
    description: str = field(default=None)
    expression: str = field(default=None)
    filterable: bool = True
    groupby: bool = True
    is_dttm: bool = False
    python_date_format: str = field(default=None)
    type: SerializableOptional[str] = field(default=None)  # native database type, e.g. "VARCHAR(255)"
    type_generic: SerializableOptional[GenericDataType] = field(default=None)

    # Newer fields, as returned in the API JSON
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

    timeGrain: SerializableOptional[TimeGrain] = field(default=None)
    columnType: SerializableOptional[ColumnType] = field(default=None)

    # Newer fields
    optionName: SerializableOptional[str] = field(default=None)
    datasourceWarning: SerializableOptional[bool] = field(default=None)

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.column, AdhocMetricColumn) and self.column.is_empty():
            self.column: SerializableOptional[AdhocMetricColumn] = None


# A string metric is the name of a metric saved in the dataset (free text, e.g. "count").
Metric = AdhocMetric | str
OrderByTyping = tuple[Metric, bool]


@dataclass(frozen=True)
class OrderBy:
    """Automatic ordering when adding a metric.

    `automate` generates the metric's orderby; `sort_ascending` sets the direction. Immutable, so that
    the instance used as the default value of the add_*_metric methods can be shared.
    """
    automate: bool = True
    sort_ascending: bool = True

    def __str__(self):
        return f'automate: {self.automate}, sort_ascending: {self.sort_ascending}'


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
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(message='A simple metric is the name of a metric saved in the dataset.',
                                  solution='Pass the metric name, e.g. "count", or use add_custom_metric.')

    @classmethod
    def check_aggregate(cls, value):
        list_aggregates = [e.value for e in MetricType]
        if str(value).upper() not in list_aggregates:
            raise ValidationError(message='Aggregate not found.',
                                  solution='Use the types.MetricType enum')


@dataclass
class MetricsListMixin:
    metrics: list[Metric] = object_field(cls=AdhocMetric, default_factory=list)

    def _editable_metrics(self) -> list:
        if not isinstance(self.metrics, list):
            self.metrics = []
        return self.metrics

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self._editable_metrics().append(metric)

    def _add_custom_metric(self,
                           label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self._editable_metrics().append(metric)


@dataclass
class SingleMetricMixin:
    metric: Metric = object_field(cls=AdhocMetric, default=None)
    # Absent unless the plugin has the control (pie: default true; word_cloud: set by automatic ordering).
    sort_by_metric: SerializableOptional[bool] = None
    # Whether the automatic ordering of add_*_metric maps to sort_by_metric (False for big numbers).
    _sorts_by_metric: SerializableNotToJson[bool] = True

    def _sort_by_metric(self, automatic_order: OrderBy) -> None:
        if self._sorts_by_metric and automatic_order and automatic_order.automate:
            self.sort_by_metric = True

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        MetricHelper.check_metric(metric)
        self.metric = metric
        self._sort_by_metric(automatic_order)

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        if not aggregate:
            raise ValidationError(message='Argument aggregate cannot be empty.')
        self._sort_by_metric(automatic_order)
        self.metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)

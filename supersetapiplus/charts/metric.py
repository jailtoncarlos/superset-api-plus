import logging
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.types import (
    ColumnType,
    FilterExpressionType,
    GenericDataType,
    MetricType,
    TimeGrain,
)
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

logger = logging.getLogger(__name__)


class AdhocMetricColumn(ApiModel):
    column_name: str = ''
    id: int | None = None
    verbose_name: str | None = None
    description: str | None = None
    expression: str | None = None
    filterable: bool = True
    groupby: bool = True
    is_dttm: bool = False
    python_date_format: str | None = None
    type: SerializableOptional[str] = None  # native database type, e.g. "VARCHAR(255)"
    type_generic: SerializableOptional[GenericDataType] = None

    # Newer fields, as returned in the API JSON
    advanced_data_type: str | None = None
    is_certified: bool = False
    certification_details: str | None = None
    certified_by: str | None = None
    warning_markdown: str | None = None

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self.column_name or not self.type:
            raise ValidationError(message='At least the column_name and type fields must be informed.',
                                  solution='')

    def is_empty(self) -> bool:
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


class AdhocMetric(ApiModel):
    expressionType: FilterExpressionType = Field(default_factory=lambda: FilterExpressionType.CUSTOM_SQL)
    sqlExpression: str | None = None
    label: SerializableOptional[str] = ''
    hasCustomLabel: SerializableOptional[bool] = None
    column: AdhocMetricColumn | None = None
    aggregate: MetricType | None = None

    timeGrain: SerializableOptional[TimeGrain] = None
    columnType: SerializableOptional[ColumnType] = None

    # Newer fields
    optionName: SerializableOptional[str] = None
    datasourceWarning: SerializableOptional[bool] = None

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        if isinstance(self.column, AdhocMetricColumn) and self.column.is_empty():
            self.column = None


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

    def __str__(self) -> str:
        return f'automate: {self.automate}, sort_ascending: {self.sort_ascending}'


class _CountUnlessSql:
    """Default aggregate of get_metric: COUNT for a simple metric, none for a SQL expression."""


_COUNT_UNLESS_SQL = _CountUnlessSql()


class MetricHelper:
    @classmethod
    def get_metric(cls, label: str,
                   column: AdhocMetricColumn | None = None,
                   sql_expression: str | None = None,
                   aggregate: MetricType | str | None | _CountUnlessSql = _COUNT_UNLESS_SQL) -> AdhocMetric:
        """Adhoc metric: an aggregate of a column (SIMPLE) or a SQL expression (SQL).

        A SQL metric takes neither a column nor an aggregate, and needs a label: without one Superset names
        the result column after the expression (``get_metric_name``, superset/utils/core.py, 6.1.0).
        """
        if isinstance(aggregate, _CountUnlessSql):
            aggregate = None if sql_expression else MetricType.COUNT
        expression_type = FilterExpressionType.CUSTOM_SQL if sql_expression else FilterExpressionType.SIMPLE
        if sql_expression:
            cls.check_sql_metric(label, column, aggregate)
        if aggregate:
            cls.check_aggregate(aggregate)
        metric = AdhocMetric(expressionType=expression_type, hasCustomLabel=bool(label), column=column,
                             sqlExpression=sql_expression,
                             aggregate=MetricType(str(aggregate).upper()) if aggregate else None)
        if label:
            metric.label = label
        return metric

    @classmethod
    def check_metric(cls, value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(message='A simple metric is the name of a metric saved in the dataset.',
                                  solution='Pass the metric name, e.g. "count", or use add_custom_metric.')

    @classmethod
    def check_sql_metric(cls, label: str, column: object, aggregate: object) -> None:
        if column is not None or aggregate:
            raise ValidationError(message='A SQL metric takes neither a column nor an aggregate.',
                                  solution='Write the aggregation in the SQL expression, e.g. "SUM(total)".')
        if not label or not label.strip():
            raise ValidationError(message='A SQL metric needs a label.',
                                  solution='Pass the label shown for the metric (the column name of the result).')

    @classmethod
    def check_aggregate(cls, value: object) -> None:
        list_aggregates = [e.value for e in MetricType]
        if str(value).upper() not in list_aggregates:
            raise ValidationError(message='Aggregate not found.',
                                  solution='Use the types.MetricType enum')


class MetricsListMixin(ApiModel):
    # MissingField when the key was absent in the JSON read, or the plugin has no metrics control.
    metrics: list[Metric] | MissingField = Field(default_factory=list)

    def _editable_metrics(self) -> list[Metric]:
        if not isinstance(self.metrics, list):
            self.metrics = []
        return self.metrics

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy) -> None:
        MetricHelper.check_metric(metric)
        self._editable_metrics().append(metric)

    def _add_custom_metric(self,
                           label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn | None,
                           sql_expression: str | None = None,
                           aggregate: MetricType | str | None = None) -> None:
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self._editable_metrics().append(metric)


class SingleMetricMixin(ApiModel):
    metric: Metric | None = None
    # Absent unless the plugin has the control (pie: default true; word_cloud: set by automatic ordering).
    sort_by_metric: SerializableOptional[bool] = None
    # Whether the automatic ordering of add_*_metric maps to sort_by_metric (False for big numbers).
    _sorts_by_metric: ClassVar[bool] = True

    def _sort_by_metric(self, automatic_order: OrderBy) -> None:
        if self._sorts_by_metric and automatic_order and automatic_order.automate:
            self.sort_by_metric = True

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy) -> None:
        MetricHelper.check_metric(metric)
        self.metric = metric
        self._sort_by_metric(automatic_order)

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn | None,
                           sql_expression: str | None = None,
                           aggregate: MetricType | str | None = None) -> None:
        if not aggregate and not sql_expression:
            raise ValidationError(message='Argument aggregate cannot be empty.',
                                  solution='Pass an aggregate, or a sql_expression for a SQL metric.')
        self._sort_by_metric(automatic_order)
        self.metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)

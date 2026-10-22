import logging
from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.fields import default_string, object_field
from supersetapiplus.base.sentinels import MissingField
from supersetapiplus.charts.filters import AdhocFilterClause
from supersetapiplus.charts.metric import (
    AdhocMetric,
    AdhocMetricColumn,
    MetricHelper,
    MetricsListMixin,
    OrderByTyping,
)
from supersetapiplus.charts.queries import CurrencyFormat
from supersetapiplus.charts.types import (
    ChartType,
    FilterClausesType,
    FilterExpressionType,
    FilterOperatorType,
    LegendOrientationType,
    LegendType,
    MetricType,
    ResultFormat,
    ResultType,
    TimeGrain,
)
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional

logger = logging.getLogger(__name__)


@dataclass
class ChartVisualOptionsMixin:
    color_scheme: str = default_string(default='supersetColors')
    show_legend: SerializableOptional[bool] = True
    legendType: LegendType = field(default_factory=lambda: LegendType.SCROLL)
    legendOrientation: LegendOrientationType = field(default_factory=lambda: LegendOrientationType.TOP)
    legendMargin: str = None
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)


@dataclass
class OptionListGroupByMixin:
    groupby: list[OrderByTyping] = object_field(cls=AdhocMetric, default_factory=list)

    # por padrão, todo mundo exige groupby
    _require_groupby: SerializableNotToJson[bool] = True

    def validate(self):
        super().validate()
        # só valida se a subclasse não desativou
        if self._require_groupby \
                and not isinstance(self.groupby, MissingField) \
                and not self.groupby:
            raise ValidationError(
                message='Field groupby cannot be empty.',
                solution='Use one of the add_simple_groupby or add_custom_groupby methods to add a groupby.'
            )

    def _add_simple_groupby(self, column_name: str):
        self.groupby.append(column_name)

    def _add_custom_groupby(self, label: str,
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        if column:
            metric.expressionType = FilterExpressionType.CUSTOM_SQL
            column.expressionType = FilterExpressionType.CUSTOM_SQL
        self.groupby.append(metric)


@dataclass
class Option(MetricsListMixin, OptionListGroupByMixin, SerializableModel):
    viz_type: ChartType = field(default=None)
    slice_id: SerializableOptional[int] = field(default=None)

    datasource: str = field(default=None)

    extra_form_data: dict = field(default_factory=dict)
    row_limit: int = 100

    adhoc_filters: list[AdhocFilterClause] = object_field(cls=AdhocFilterClause, default_factory=list)
    dashboards: list[int] = field(default_factory=list)

    force: SerializableOptional[bool] = field(default=None)
    result_format: SerializableOptional[ResultFormat] = field(default=None)
    result_type: SerializableOptional[ResultType] = field(default=None)

    cache_timeout: SerializableOptional[int] = field(default=None)
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default=None)
    order_desc: SerializableOptional[bool] = field(default=None)

    comparison_type: SerializableOptional[str] = field(default=None)

    def validate(self):
        super().validate()

    def __post_init__(self):
        super().__post_init__()
        if not self.groupby:
            self.groupby: list[OrderByTyping] = []

    def add_dashboard(self, dashboard_id):
        dashboards = set(self.dashboards)
        dashboards.add(dashboard_id)
        self.dashboards = list(dashboards)

    def _adhoc_filters(self,
                       expression_type: FilterExpressionType,
                       clause: FilterClausesType,
                       subject: str = None,
                       comparator: str = None,
                       sql_expression=None,
                       operator: FilterOperatorType = None) -> None:
        operator_id = None
        if operator:
            operator_id = operator.name

        adhoc_filter_clause = AdhocFilterClause(expressionType=expression_type,
                                                subject=subject,
                                                operator=operator,
                                                operatorId=operator_id,
                                                comparator=comparator,
                                                clause=clause,
                                                sqlExpression=sql_expression)
        self.adhoc_filters.append(adhoc_filter_clause)

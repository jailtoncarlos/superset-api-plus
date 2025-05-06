import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, runtime_checkable, Protocol

from supersetapiplus.base.base import SerializableModel, object_field
from supersetapiplus.charts.filters import AdhocFilterClause
from supersetapiplus.charts.metric import OrderByTyping, AdhocMetricColumn, MetricHelper, AdhocMetric, OrderBy
from supersetapiplus.charts.types import ChartType, FilterOperatorType, FilterClausesType, \
    FilterExpressionType, MetricType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableOptional

logger = logging.getLogger(__name__)



@runtime_checkable
class SupportsGroupBy(Protocol):
    # This is a protocol that defines the expected structure of classes that have metric.
    groupby: Optional[List[OrderByTyping]]


class OptionListGroupByMixin:
    def _add_simple_groupby(self: SupportsGroupBy, column_name:str):
        self.groupby.append(column_name)

    def _add_custom_groupby(self: SupportsGroupBy, label: str,
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        if column:
            metric.expressionType = FilterExpressionType.CUSTOM_SQL
            column.expressionType = FilterExpressionType.CUSTOM_SQL
        self.groupby.append(metric)


@dataclass
class Option(SerializableModel, OptionListGroupByMixin):
    viz_type: ChartType = None
    slice_id: Optional[int] = None

    datasource: str = None

    extra_form_data: Dict = field(default_factory=dict)
    row_limit: int = 100

    adhoc_filters: List[AdhocFilterClause] = object_field(cls=AdhocFilterClause, default_factory=list)
    dashboards: List[int] = field(default_factory=list)
    groupby: Optional[List[OrderByTyping]] = object_field(cls=AdhocMetric, default_factory=list)

    timeseries_limit_metric: Optional[AdhocMetric] = object_field(cls=AdhocMetric, default_factory=AdhocMetric)

    force: SerializableOptional[bool] = False
    result_format: SerializableOptional[str] = "json"
    result_type: SerializableOptional[str] = "full"

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        raise NotImplementedError("This method should be implemented in the subclass")

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        raise NotImplementedError("This method should be implemented in the subclass")

    def __post_init__(self):
        super().__post_init__()
        if not self.groupby:
            self.groupby: List[OrderByTyping] = []

    def validate(self, data: dict):
        super().validate(data)
        if not self.groupby:
            raise ValidationError(message='Field groupy cannot be empty.',
                                  solution='Use one of the add_simple_groupby or add_custom_groupby methods to add a groupby.')

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




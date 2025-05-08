from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List

from supersetapiplus.base.base import SerializableModel, object_field
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.metric import OrderBy, AdhocMetric
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, AdhocMetricColumn
from supersetapiplus.charts.types import FilterOperatorType, FilterClausesType, MetricType, FilterExpressionType, \
    ResultFormat, ResultType
from supersetapiplus.exceptions import ChartValidationError, ValidationError
from supersetapiplus.typing import SerializableOptional


@dataclass
class FormData(Option):
    pass


@dataclass
class QueryContext(SerializableModel):
    datasource: DataSource = object_field(cls=DataSource, default_factory=DataSource)
    queries: List[Query] = object_field(cls=Query, default_factory=list)
    form_data: FormData = object_field(cls=FormData, default_factory=FormData)

    force: bool = False
    result_format: SerializableOptional[ResultFormat] = field(default_factory=lambda: ResultFormat.JSON)
    result_type: SerializableOptional[ResultType] = field(default_factory=lambda: ResultType.FULL)


    @abstractmethod
    def _default_query_object_class(self) -> type[Query]:
        raise NotImplementedError()

    def __post_init__(self):
        self._automatic_order: OrderBy = None

    @property
    def automatic_order(self):
        if not hasattr(self, '_automatic_order'):
            self._automatic_order: OrderBy = None
        return self._automatic_order

    def validate(self):
        if not self.queries:
            raise ValidationError(message='Field queries cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')

        for query in self.queries:
            query.validate()

    def add_dashboard(self, dashboard_id):
        self.form_data.add_dashboard(dashboard_id)

    @property
    def first_queries(self):
        if self.queries and len(self.queries) > 1:
            raise ChartValidationError("""There are more than one query in the queries list.
                                       We don't know which one to include the filter in.""")
        if not self.queries:
            QueryObjectClass = self._default_query_object_class()
            self.queries: List[QueryObjectClass] = []
        if len(self.queries) == 0:
            QueryObjectClass = self._default_query_object_class()
            self.queries.append(QueryObjectClass())
        return self.queries[-1]

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        self._automatic_order = automatic_order
        self.form_data._add_simple_metric(metric, automatic_order)
        self.first_queries._add_simple_metric(metric, automatic_order)
        if automatic_order.automate:
            self._add_simple_orderby(metric, automatic_order.sort_ascending)

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn = None,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        self._automatic_order = automatic_order
        self.form_data._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        self.first_queries._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        if automatic_order and automatic_order.automate:
            self._add_custom_orderby(label, automatic_order.sort_ascending, column, sql_expression, aggregate)

    def _add_simple_orderby(self, column_name: str,
                            sort_ascending: bool = True):
        self.first_queries._add_simple_orderby(column_name, sort_ascending)

    def _add_custom_orderby(self, label: str,
                            sort_ascending: bool,
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        self.first_queries._add_custom_orderby(label, sort_ascending, column, sql_expression, aggregate)

    def _add_simple_groupby(self, column_name: str):
        self.form_data._add_simple_groupby(column_name)
        self.first_queries._add_simple_columns(column_name)

    def _add_custom_groupby(self, label: str,
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None):
        self.form_data._add_custom_groupby(label, column, sql_expression, aggregate)
        self.first_queries._add_custom_columns(label, column, sql_expression, aggregate)

    def _add_simple_filter(self, column_name: str,
                           value: str,
                           operator: FilterOperatorType = FilterOperatorType.EQUALS) -> None:
        self.form_data._adhoc_filters(expression_type=FilterExpressionType.SIMPLE,
                                   clause=FilterClausesType.WHERE,
                                   subject=column_name,
                                   comparator=value,
                                   operator=operator)
        self.first_queries._add_simple_filter(column_name, value, operator)


    def _add_extra_where(self, sql: str):
        self.form_data._adhoc_filters(expression_type=FilterExpressionType.CUSTOM_SQL,
                                   clause=FilterClausesType.WHERE,
                                   sql_expression=sql)
        self.first_queries._add_extra_where(sql)

    def _add_extra_having(self, sql: str):
        self.first_queries._add_extra_having(sql)
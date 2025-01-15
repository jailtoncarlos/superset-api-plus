import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from supersetapiclient.base.base import Object, ObjectField
from supersetapiclient.base.datasource import DataSource
from supersetapiclient.charts.options import Option
from supersetapiclient.charts.queries import QueryObject, AdhocMetricColumn, OrderBy, ColumnsMixin
from supersetapiclient.charts.types import FilterOperatorType, FilterClausesType, MetricType, FilterExpressionType
from supersetapiclient.exceptions import ChartValidationError, ValidationError


@dataclass
class FormData(Option):
    pass


@dataclass
class QueryContext(Object, ABC):
    datasource: DataSource = ObjectField(cls=DataSource, default_factory=DataSource)
    queries: List[QueryObject] = ObjectField(cls=QueryObject, default_factory=list)
    form_data: FormData = ObjectField(cls=FormData, default_factory=FormData)

    def __post_init__(self):
        self._automatic_order: OrderBy = None

    @property
    def automatic_order(self):
        if not hasattr(self, '_automatic_order'):
            self._automatic_order: OrderBy = None
        return self._automatic_order

    def validate(self, data: dict):
        super().validate(data)
        if not self.queries:
            raise ValidationError(message='Field queries cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')

        for query in self.queries:
            query.validate(data)

    def add_dashboard(self, dashboard_id):
        self.form_data.add_dashboard(dashboard_id)

    @abstractmethod
    def _get_query_object_class(self):
        raise NotImplementedError()

    @property
    def first_queries(self):
        if self.queries and len(self.queries) > 1:
            raise ChartValidationError("""There are more than one query in the queries list.
                                       We don't know which one to include the filter in.""")
        if not self.queries:
            QueryObjectClass = self._get_query_object_class()
            self.queries: List[QueryObjectClass] = []
        if len(self.queries) == 0:
            QueryObjectClass = self._get_query_object_class()
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
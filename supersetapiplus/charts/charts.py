"""Charts."""
import copy
import json
from dataclasses import dataclass, field
from typing import List
from typing_extensions import Self

from supersetapiplus.base.base import Object, ObjectFactories, default_string, raise_for_status, ObjectField
from supersetapiplus.base.types import DatasourceType
from supersetapiplus.charts.filters import AdhocFilterClause
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import QueryFilterClause, QueryObject, Column, AdhocMetricColumn, OrderBy

from supersetapiplus.charts.query_context import QueryContext, DataSource
from supersetapiplus.charts.types import ChartType, FilterOperatorType, FilterClausesType, FilterExpressionType, \
    MetricType, MetricType
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.itemposition import ItemPosition
from supersetapiplus.exceptions import NotFound, ChartValidationError, ValidationError
from supersetapiplus.typing import NotToJson, Optional
from supersetapiplus.utils import dict_compare


@dataclass
class Chart(Object):
    JSON_FIELDS = ['params', 'query_context']

    slice_name: str
    datasource_id: int = None
    description: Optional[str] = field(default=None)

    viz_type: ChartType = None

    # For post charts, optional fields are not used.
    id: NotToJson[int] = None

    cache_timeout: NotToJson[int] = field(default=None)

    params: Option = field(default_factory=Option)
    query_context: QueryContext = ObjectField(cls=QueryContext, default_factory=QueryContext)

    datasource_type: DatasourceType = DatasourceType.TABLE
    dashboards: List[Dashboard] = ObjectField(cls=Dashboard, default_factory=list)

    _slice_name_override: NotToJson[str] = default_string()

    def __post_init__(self):
        super().__post_init__()
        from supersetapiplus.dashboards.dashboards import Dashboard
        self._dashboards = [Dashboard(dashboard_title='')]

        if self.id is None:
            if self.datasource_id is None:
                raise ChartValidationError("""
                    When id is None, argument datasource id becomes mandatory. 
                    We recommend using the [client_superset].datasets.get_id_by_name('name_dataset') method 
                    to get the dataset id by name.
                """)

            if self.params.datasource is None:
                self.query_context.datasource.id = self.datasource_id
                self.params.datasource = f'{self.datasource_id}__{self.datasource_type}'
                self.query_context.form_data = self.params.datasource

    def validate(self, data: dict):
        super().validate(data)
        if self.params != self.query_context.form_data:
            added, removed, modified, same = dict_compare(self.params.to_dict(), self.query_context.form_data.to_dict())

            raise ValidationError(message=f'self.params is not the same as self.query_conext.form_data. Diff: {modified}',
                                  solution="We recommend using the public methods of the chart class.")

    @classmethod
    def instance(cls,
                 slice_name: str,
                 datasource: DataSource,
                 options: Option = Option()):

        new_chart = cls(slice_name=slice_name,
                        datasource_id=datasource.id,
                        datasource_type=datasource.type)

        options.datasource = f'{datasource.id}__{datasource.type}'
        # options.groupby = groupby

        ClassQuerie = QueryObject.get_class(type_=str(new_chart.viz_type))

        # query = ClassQuerie(columns=groupby)
        # new_chart.query_context.queries.append(query)

        new_chart.params = options
        new_chart.query_context.form_data = copy.deepcopy(options)
        return new_chart

    def add_dashboard(self, dashboard):
        self.dashboards.append(dashboard)
        self.query_context.add_dashboard(dashboard.id)

    def clone(self, slice_name: str = None, slice_name_override: str = None, clear_dashboard: bool = False,
              clear_filter: bool = True) -> Self:
        new_chart = copy.deepcopy(self)
        new_chart.slice_name = slice_name or f'{new_chart.slice_name}_clone'
        new_chart._slice_name_override = slice_name_override or f'Chart clone de {new_chart.slice_name}'
        new_chart.id = 0

        if clear_dashboard:
            new_chart.dashboards = []
        if clear_filter:
            new_chart.clear_filter()

        return new_chart

    def clear_filter(self) -> None:
        self.params.adhoc_filters = []
        for query in self.query_context.queries:
            query.filters = []
        self.query_context.form_data.adhoc_filters = []

    def add_simple_metric(self, metric: MetricType, automatic_order: OrderBy = OrderBy()):
        self.params._add_simple_metric(metric, automatic_order)
        self.query_context._add_simple_metric(metric, automatic_order)

    def add_custom_metric(self, label: str,
                          automatic_order: OrderBy = OrderBy(),
                          column: AdhocMetricColumn = None,
                          sql_expression: str = None,
                          aggregate: MetricType = None):
        if column:
            column.id = self.id
        self.params._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        self.query_context._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)


    def add_simple_orderby(self, column_name: str,
                            sort_ascending: bool = True):
        self.query_context._add_simple_orderby(column_name, sort_ascending)

    def add_custom_orderby(self, label: str,
                             sort_ascending: bool,
                             column: AdhocMetricColumn = None,
                             sql_expression: str = None,
                             aggregate: MetricType = None):
        self.query_context._add_custom_orderby(label, sort_ascending, column, sql_expression, aggregate)

    def add_simple_dimension(self, column_name: str):
        self.params._add_simple_groupby(column_name)
        self.query_context._add_simple_groupby(column_name)

    def add_custom_dimension(self, label: str,
                             column: AdhocMetricColumn = None,
                             sql_expression: str = None,
                             aggregate: MetricType = None):
        self.params._add_custom_groupby(label, column, sql_expression, aggregate)
        self.query_context._add_custom_groupby(label, column, sql_expression, aggregate)

    def add_simple_filter(self, column_name: str,
                          value: str,
                          operator: FilterOperatorType = FilterOperatorType.EQUALS) -> None:
        self.params._adhoc_filters(expression_type=FilterExpressionType.SIMPLE,
                                   clause=FilterClausesType.WHERE,
                                   subject=column_name,
                                   comparator=value,
                                   operator=operator)
        self.query_context._add_simple_filter(column_name=column_name,
                                              value=value,
                                              operator=operator)

    def add_extra_where(self, sql: str):
        self.params._adhoc_filters(expression_type=FilterExpressionType.CUSTOM_SQL,
                                   clause=FilterClausesType.WHERE,
                                   sql_expression=sql)
        self.query_context._add_extra_where(sql)

    def add_extra_having(self, sql: str):
        self.query_context._add_extra_having(sql)

    def to_json(self, columns=None):
        data = super().to_json(columns).copy()

        dashboards = set()
        for dasboard in self.dashboards:
            dashboards.add(dasboard.id)
        data['dashboards'] = list(dashboards)
        return data

    @classmethod
    def from_json(cls, data: dict):
        obj = super().from_json(data)
        obj._dashboards = obj.dashboards

        # set default datasource
        if obj.query_context:
            datasource = obj.query_context.datasource
            if datasource:
                obj.datasource_id = datasource.id
                obj.datasource_type = datasource.type

        return obj


class Charts(ObjectFactories):
    endpoint = "chart/"
    base_object = Chart

    def get_base_object(self, data):
        type_ = data['viz_type']
        if type_:
            m = self.base_object.__module__.split('.')
            m.pop(-1)
            m.append(type_)
            module_name = '.'.join(m)
            return self.base_object.get_class(type_, module_name)
        return self.base_object

    def get_chart_data(self, slice_id: str, dashboard_id: int) -> dict:
        chart = self.client.charts.get(slice_id)
        dashboard_exists = False
        for id in chart.params.dashboards:
            if dashboard_id == id:
                dashboard_exists = True
        if not dashboard_exists:
            raise NotFound(f'Dashboard id {dashboard_id} does not exist.')

        # 'http://localhost:8088/api/v1/chart/data?form_data=%7B%22slice_id%22%3A347%7D&dashboard_id=12&force'
        query = {
            "slice_id": slice_id,
            "dashboard_id": dashboard_id,
            "force": None
        }
        params = {"data": json.dumps(query)}
        payload = {
            'datasource': chart.query_context.datasource.to_json(),
            'force': chart.force,
            'queries': chart.query_context.queries.to_json(),
            'form_data': chart.query_context.form_data.to_json(),
            'result_format': chart.result_format,
            'result_type': chart.result_type
        }

        response = self.client.get(self.base_url,
                                   params=params,
                                   json=payload)

        raise_for_status(response)
        return response.json().result('result')

    def add(self, chart: Chart, title: str, parent: ItemPosition = None, update_dashboard=True) -> int:
        id = super().add(chart)

        try:
            if update_dashboard and chart.dashboards:
                dashboard_id = chart.dashboards[0].id
                dashboard = self.client.dashboards.get(dashboard_id)
                dashboard.add_chart(chart, title)
                dashboard.save()
        except:
            self.delete(id)
            raise
        return id

    def add_to_dashboard(self, chart: Chart, dashboard_id=int):
        url = self.client.join_urls(self.base_url, "/data")
        query = {
            'slice_id': chart.id,
            'dashboard_id': dashboard_id,
            'force': None
        }
        params = {"form_data": json.dumps(query)}
        payload = chart.query_context.to_dict()
        response = self.client.post(url, params=params, json=payload)
        raise_for_status(response)
        return response.json()

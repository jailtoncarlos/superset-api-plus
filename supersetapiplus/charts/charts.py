"""Charts."""
import copy
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass, field

from typing_extensions import Self

from supersetapiplus.base.base import ApiModelFactories, SerializableModel
from supersetapiplus.base.fields import object_field
from supersetapiplus.base.types import DatasourceType
from supersetapiplus.charts.build_query import query_context_for
from supersetapiplus.charts.metric import OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import AdhocMetricColumn
from supersetapiplus.charts.query_context import DataSource, QueryContext
from supersetapiplus.charts.types import ChartType, FilterClausesType, FilterExpressionType, FilterOperatorType, MetricType
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import ChartValidationError, DashboardValidationError, NotFound, ValidationError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.utils.dict_utils import detailed_dict_diff

logger = logging.getLogger(__name__)


@dataclass
class Chart(SerializableModel):
    JSON_FIELDS = ['params', 'query_context']
    PRESERVE_EXTRA_FIELDS = False
    # Fields accepted by the API (OpenAPI 6.1.0: ChartRestApi.post / ChartRestApi.put).
    POST_FIELDS = (
        "cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
        "datasource_name", "datasource_type", "description", "external_url", "is_managed_externally",
        "owners", "params", "query_context", "query_context_generation", "slice_name", "viz_type",
    )
    PUT_FIELDS = (
        "cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
        "datasource_type", "description", "external_url", "is_managed_externally", "owners", "params",
        "query_context", "query_context_generation", "slice_name", "tags", "viz_type",
    )
    # Fields that Superset legitimately keeps different between params and
    # query_context.form_data: identity (stale slice_id after dashboard import/export)
    # and request parameters that the frontend injects only into form_data.
    VOLATILE_FORM_DATA_FIELDS = {'slice_id', 'dashboards', 'force', 'result_format', 'result_type'}
    # Suffixes of keys that Superset stores in params but may omit from query_context.form_data
    # (e.g. the query B keys of mixed_timeseries). Only absence is tolerated, not diverging values.
    PARAMS_ONLY_FIELD_SUFFIXES = ()

    slice_name: str
    id: int = field(default=None)
    description: str = field(default=None)
    viz_type: ChartType = field(default=None)

    certification_details: str = field(default=None)
    certified_by: str = field(default=None)
    is_managed_externally: bool = field(default=None)

    params: Option = field(init=False)  # Do not instantiate Option directly!
    query_context: QueryContext = object_field(cls=QueryContext, default_factory=QueryContext)

    datasource_id: SerializableOptional[int] = field(default=None)
    datasource_type: SerializableOptional[DatasourceType] = field(default=None)
    cache_timeout: int = field(default=None)

    dashboards: SerializableNotToJson[list[Dashboard]] = object_field(cls=Dashboard, default_factory=list)
    owners: SerializableNotToJson[list[dict]] = field(default=None)

    tags: SerializableNotToJson[list] = field(default=None)

    changed_on_delta_humanized: SerializableNotToJson[str] = None
    _slice_name_override: SerializableNotToJson[str] = field(default=None)
    thumbnail_url: SerializableNotToJson[str] = field(default=None)
    url: SerializableNotToJson[str] = field(default=None)


    @classmethod
    @abstractmethod
    def _default_option_class(cls) -> type[Option]:
        ...

    def __post_init__(self):
        super().__post_init__()
        from supersetapiplus.dashboards.dashboards import Dashboard
        self._dashboards = [Dashboard(dashboard_title='')]

        if not hasattr(self, "params") or self.params is None:
            self.params = self._default_option_class()()  # Assumes the concrete subclass defines this method

        # Charts built in code send the query_context the Superset UI would derive from params
        # (build_query); charts read from Superset keep the stored one (lossless round trip).
        self._derive_query_context = self.id is None

        if self.id is None:
            if self.datasource_id is None:
                raise ChartValidationError("""
                    When id is None, argument datasource id becomes mandatory.
                    We recommend using the [client_superset].datasets.get_id_by_name('name_dataset') method
                    to get the dataset id by name.
                """)

            self._fill_datasource()

    def _fill_datasource(self):
        """New chart: params (and query_context) get the datasource from datasource_id/datasource_type.

        Called in __post_init__ and again at the end of from_json: during from_json, __post_init__
        runs while params is still a dict (the conversion to Option happens later).
        """
        if self.id is not None or self.datasource_id is None or not isinstance(self.params, SerializableModel):
            return
        if not self.params.datasource:  # None or MissingField (absent from the JSON)
            self.params.datasource = f'{self.datasource_id}__{self.datasource_type}'
            if isinstance(self.query_context, SerializableModel):
                self.query_context.datasource.id = self.datasource_id
                self.query_context.form_data = copy.deepcopy(self.params)

    def validate(self):
        super().validate()
        # A null query_context (chart never saved from Explore) or one without form_data (example charts
        # loaded from YAML in Superset 6.1) has nothing to compare with params.
        if self.query_context is None or not isinstance(self.query_context.form_data, SerializableModel):
            return

        params = {k: v for k, v in self.params.to_dict().items() if k not in self.VOLATILE_FORM_DATA_FIELDS}
        form_data = {k: v for k, v in self.query_context.form_data.to_dict().items()
                     if k not in self.VOLATILE_FORM_DATA_FIELDS}
        # Old Superset versions stored form_data.datasource as "None__table";
        # params remains the source of truth and Superset ignores the invalid value.
        if str(form_data.get('datasource', '')).startswith('None__'):
            form_data['datasource'] = params.get('datasource')
        if self.PARAMS_ONLY_FIELD_SUFFIXES:
            params = {k: v for k, v in params.items()
                      if k in form_data or not k.endswith(self.PARAMS_ONLY_FIELD_SUFFIXES)}
        if params != form_data:
            added, removed, modified, same = detailed_dict_diff(params, form_data)

            raise ValidationError(message=f'self.params is not the same as self.query_conext.form_data. '
                                          f'Diff: modified={modified}, added={added}, removed={removed}',
                                  solution="We recommend using the public methods of the chart class.")

    @classmethod
    def instance(cls,
                 slice_name: str,
                 datasource: DataSource,
                 options: Option = None):

        if options is None:
            options = cls._default_option_class()()  # delegates to the subclass

        new_chart = cls(slice_name=slice_name,
                        datasource_id=datasource.id,
                        datasource_type=datasource.type)

        options.datasource = f'{datasource.id}__{datasource.type}'

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
        new_chart._slice_name_override = slice_name_override or f'Chart clone of {new_chart.slice_name}'
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

    def derive_query_context(self, enabled: bool = True) -> None:
        """Rebuild the query_context from params on the next save, as Explore does when the chart is saved.

        Enabled automatically for charts built in code; call it on a chart read from Superset after
        changing its params, so the stored query_context (used by /chart/{id}/data, reports and cache
        warm-up) follows them.
        """
        self._derive_query_context = enabled

    def ui_query_context(self) -> dict:
        """Query context the Superset UI derives from the current params (frontend buildQuery, 6.1.0)."""
        return query_context_for(self.params.to_dict())

    def to_json(self, columns: list = None) -> dict:
        data = super().to_json(columns).copy()
        if getattr(self, '_derive_query_context', False) and 'query_context' in data \
                and isinstance(self.params, SerializableModel):
            data['query_context'] = json.dumps(self.ui_query_context())
        return data

    @classmethod
    def from_json(cls, data: dict):
        obj = super().from_json(data)
        obj._dashboards = obj.dashboards

        # Superset keeps query_context null on charts that were never saved from Explore
        # (common in imported charts). Preserve the null instead of fabricating an empty context.
        if data.get('query_context') in (None, '', 'null'):
            obj.query_context = None

        # Datasource: GET /chart/{id} returns datasource_id/datasource_type at the top level, which prevail;
        # params.datasource may be stale (e.g. imported example charts).
        if data.get('datasource_id'):
            obj.datasource_id = int(data['datasource_id'])
            obj.datasource_type = DatasourceType(data.get('datasource_type') or 'table')
        elif obj.query_context:
            datasource = obj.query_context.datasource
            if datasource and datasource.id:
                obj.datasource_id = datasource.id
                obj.datasource_type = datasource.type
            else:
                logger.warning("datasource query_context without 'id' defined")
        elif isinstance(obj.params, SerializableModel) and '__' in str(obj.params.datasource or ''):
            # Listings with restricted columns (find(columns=[...])) do not include params: the partial
            # object has no datasource and is completed by find_one(..., full=True).
            datasource_id, datasource_type = str(obj.params.datasource).split('__', 1)
            obj.datasource_id = int(datasource_id)
            obj.datasource_type = DatasourceType(datasource_type)

        obj._fill_datasource()
        obj._derive_query_context = obj.id is None
        return obj


class Charts(ApiModelFactories):
    endpoint = "chart/"
    TYPE_COLUMN = "viz_type"

    def _default_object_class(self) -> type[SerializableModel]:
        return Chart

    def get_chart_data(self, slice_id: int, dashboard_id: int | None = None) -> list[dict]:
        """
        Chart data computed by Superset from the saved query_context (GET /chart/{pk}/data/).

        Args:
            slice_id: chart id.
            dashboard_id: if given, checks that the chart belongs to this dashboard.

        Returns:
            list[dict]: one item per query of the query_context (`data`, `colnames`, `rowcount`...).
        """
        if dashboard_id is not None and dashboard_id not in self.dashboard_ids(slice_id):
            raise NotFound(f'Chart {slice_id} does not belong to dashboard {dashboard_id}.')
        url = self.client.join_urls(self.base_url, slice_id, "data/")
        return self.client.get(url, params={"format": "json", "type": "full"}).json()["result"]

    def dashboard_ids(self, chart_id: int) -> list[int]:
        """Ids of the dashboards associated with the chart, as stored by Superset."""
        result = self.client.get(self.client.join_urls(self.base_url, chart_id)).json()["result"]
        return [d["id"] for d in result.get("dashboards") or []]

    def add_to_dashboard(self, chart: Chart | int, dashboard_id: int) -> list[int]:
        """
        Associates the chart with the dashboard (PUT /chart/{pk} with only `dashboards`), keeping existing associations.

        The association is by id on the chart: the `dashboards` field of ChartPutSchema replaces the list,
        so the current ones are read first. Returns the stored list.
        """
        chart_id = chart if isinstance(chart, int) else chart.id
        if not chart_id:
            raise ChartValidationError('Save the chart before attaching it to a dashboard (chart.id is empty).')
        current = self.dashboard_ids(chart_id)
        if dashboard_id in current:
            return current
        updated = current + [dashboard_id]
        self.client.put(self.client.join_urls(self.base_url, chart_id), json={"dashboards": updated})
        return updated

    def add_and_attach_to_dashboard(self, chart: Chart, title: str, parent=None) -> int:
        """
        Creates the chart and places it in the layout of the dashboard the source chart belongs to.

        Args:
            chart (Chart): chart to create (e.g. a clone of a chart already associated with a dashboard).
            title (str): title shown on the dashboard (sliceNameOverride).
            parent (NodePosition, optional): layout node to insert into.

        Returns:
            int: id of the created chart.

        Raises:
            DashboardValidationError: the source chart does not belong to any dashboard.
        """
        # Validate before creating: previously the chart was created and left orphaned when validation failed.
        if not chart.dashboards:
            raise DashboardValidationError(
                message="Could not attach the chart: it does not belong to any dashboard.",
                solution="Check that the given chart is associated with a dashboard before calling this method."
            )
        dashboard = self.client.dashboards.get(chart.dashboards[0].id)
        new_id = self.add(chart)
        dashboard.add_chart(chart, title, parent)
        dashboard.save()
        return new_id

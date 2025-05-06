"""Charts."""
from dataclasses import dataclass, field
from typing import List, Dict

from supersetapiplus.base.base import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import MetricsListMixin, AdhocMetric, Metric, AdhocMetricColumn, OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import ColumnConfig, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, QueryModeType, TimeGrain, MetricType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableOptional


# class TableAdhocMetric(AdhocMetric):
#     """Class to represent a table metric."""
#     sqlExpression: Optional[str] = field(init=False, repr=False, default=None)
#     aggregate: Optional[MetricType] = field(init=False, repr=False, default=None)
#     timeGrain: Optional[str] = field(init=False, repr=False, default=None)
#     columnType: Optional[ColumnType] = field(init=False, repr=False, default=None)


@dataclass
class TableOption(Option, MetricsListMixin):
    row_limit: int = 1000
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    query_mode: QueryModeType = field(default_factory=lambda: QueryModeType.AGGREGATE)

    order_by_cols: List = field(default_factory=list)

    server_pagination: SerializableOptional[bool] = field(default=None)
    server_page_length: int = 0
    order_desc: bool = False
    show_totals: SerializableOptional[bool] = field(default=None)

    cache_timeout: SerializableOptional[int] = field(default=None)

    table_timestamp_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    page_length: SerializableOptional[int] = field(default=None)
    include_search: SerializableOptional[bool] = field(default=None)
    show_cell_bars: bool = True

    align_pn: SerializableOptional[bool] = field(default=None)
    color_pn: bool = True
    allow_rearrange_columns: SerializableOptional[bool] = field(default=None)
    conditional_formatting: SerializableOptional[List] = field(default_factory=list)
    queryFields: SerializableOptional[Dict] = field(default_factory=dict)

    table_filter: SerializableOptional[bool] = field(default=None)
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default=None)
    time_range: SerializableOptional[str] = 'No filter'
    granularity_sqla: SerializableOptional[str] = field(default=None)

    metrics: SerializableOptional[List[Metric]] = object_field(cls=AdhocMetric, default_factory=list)
    column_config: SerializableOptional[Dict[str, ColumnConfig]] = object_field(cls=ColumnConfig, dict_right=True, default_factory=dict)

    temporal_columns_lookup: SerializableOptional[dict] = field(default=None)
    all_columns: SerializableOptional[list] = field(default_factory=list)
    percent_metrics: SerializableOptional[list] = field(default_factory=list)
    allow_render_html: SerializableOptional[bool] = True
    comparison_color_scheme: SerializableOptional[str] = field(default=None)
    comparison_type: SerializableOptional[str] = field(default=None)
    annotation_layers: SerializableOptional[list] = field(default=None)

    time_range: SerializableOptional[str] = field(default=None)
    force: SerializableOptional[bool] = field(default=None)
    result_format: SerializableOptional[str] = field(default=None)  # "json"
    result_type: SerializableOptional[str] = field(default=None)  # "full"

    def __post_init__(self):
        super().__post_init__()
        if not self.metrics:
            self.metrics: List[Metric] = []
        if self.server_page_length == 0:
            self.server_page_length = 10

    def validate(self, data: dict):
        super().validate(data)
        if not self.metrics:
            raise ValidationError(message='Field metrics cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')

    def _add_column_config(self, label:str, column_config:ColumnConfig):
        self.column_config[label] = column_config


@dataclass
class TableFormData(TableOption):
    pass


@dataclass
class TableQueryObject(Query):
    time_range: SerializableOptional[str] = field(init=False, default='No Filter')
    granularity: SerializableOptional[str] = None
    # applied_time_extras: List[str] = field(default_factory=list)

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy):
        #In the table the option is sort descending
        automatic_order.sort_ascending = not automatic_order.sort_ascending
        super()._add_simple_metric(metric, automatic_order)

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn = None,
                           sql_expression: str = None,
                           aggregate: MetricType = None):
        #In the table the option is sort descending
        automatic_order.sort_ascending = not automatic_order.sort_ascending
        super()._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)


@dataclass
class TableQueryContext(QueryContext):
    form_data: TableFormData = object_field(cls=TableFormData, default_factory=TableFormData)
    queries: List[TableQueryObject] = object_field(cls=Query, default_factory=list)

    def validate(self, data: dict):
        super().validate(data)
        if self.form_data.metrics or self.queries:
            equals = False
            counter = 0
            for form_data_metric in self.form_data.metrics:
                for query in self.queries:
                    for query_metric in query.metrics:
                        if form_data_metric == query_metric:
                            counter+=1
            if counter == len(self.form_data.metrics):
                equals = True

            if not equals:
                raise ValidationError(message='The metrics definition in formdata is not included in queries.metrics.',
                                      solution="We recommend using one of the Chart class's add_simple_metric or add_custom_metric methods to ensure data integrity.")

    def _default_query_object_class(self) -> type[Query]:
        return TableQueryObject


@dataclass
class TableChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    params: TableOption = object_field(cls=TableOption, default_factory=TableOption)
    query_context: TableQueryContext = object_field(cls=TableQueryContext, default_factory=TableQueryContext)

    # Campos adicionais presentes no dicionário da API
    certification_details: str | None = None
    certified_by: str | None = None
    changed_on_delta_humanized: str | None = None
    is_managed_externally: bool = False
    owners: list[dict] = field(default_factory=list)
    tags: list = field(default_factory=list)
    thumbnail_url: str | None = None
    url: str | None = None

    def add_simple_metric(self, metric: MetricType,
                          automatic_order: OrderBy = OrderBy(),
                          column_config: ColumnConfig = None):
        super().add_simple_metric(metric, automatic_order)
        if column_config:
            self.params._add_column_config(str(metric), column_config)
            self.query_context.form_data._add_column_config(str(metric), column_config)


    def add_custom_metric(self, label: str,
                            automatic_order: OrderBy = OrderBy(),
                            column: AdhocMetricColumn = None,
                            sql_expression: str = None,
                            aggregate: MetricType = None,
                            column_config: ColumnConfig = None):
        super().add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        if column_config:
            self.params._add_column_config(label, column_config)
            self.query_context.form_data._add_column_config(label, column_config)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TableOption
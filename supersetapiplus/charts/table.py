"""Charts."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from supersetapiplus.base.base import object_field
from supersetapiplus.base.fields import MissingField
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import MetricsListMixin, AdhocMetric, Metric, AdhocMetricColumn, OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import ColumnConfig, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, QueryModeType, TimeGrain, MetricType, ResultFormat, \
    ResultType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableOptional, SerializableNotToJson


@dataclass
class TableOptionBase(Option):
    conditional_formatting: SerializableOptional[List] = field(default_factory=list)
    temporal_columns_lookup: SerializableOptional[dict] = field(default=None)
    annotation_layers: SerializableOptional[list] = field(default=None)


@dataclass
class TableOption(TableOptionBase):
    row_limit: int = 1000
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    query_mode: QueryModeType = field(default_factory=lambda: QueryModeType.AGGREGATE)

    order_by_cols: List = field(default_factory=list)

    server_pagination: SerializableOptional[bool] = field(default=None)
    server_page_length: SerializableOptional[int] = field(default=None)
    show_totals: SerializableOptional[bool] = field(default=None)

    table_timestamp_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    page_length: int = field(default=None)
    include_search: SerializableOptional[bool] = field(default=None)
    show_cell_bars: bool = True

    align_pn: SerializableOptional[bool] = field(default=None)
    color_pn: bool = True
    allow_rearrange_columns: SerializableOptional[bool] = field(default=None)

    table_filter: SerializableOptional[bool] = field(default=None)
    granularity_sqla: SerializableOptional[str] = field(default=None)

    column_config: SerializableOptional[Dict[str, ColumnConfig]] = object_field(cls=ColumnConfig, dict_right=True, default_factory=dict)

    all_columns: SerializableOptional[list] = field(default_factory=list)
    percent_metrics: SerializableOptional[list] = field(default_factory=list)
    allow_render_html: SerializableOptional[bool] = True
    comparison_color_scheme: SerializableOptional[str] = field(default=None)

    timeseries_limit_metric: Optional[Metric] = object_field(default=None)

    force: SerializableOptional[bool] = field(default=None)
    result_format: SerializableOptional[ResultFormat] = field(default=None)
    result_type: SerializableOptional[ResultType] = field(default=None)

    def __post_init__(self):
        super().__post_init__()
        if not self.metrics:
            self.metrics: List[Metric] = []
        if self.server_page_length == 0:
            self.server_page_length = 10

    def validate(self):
        super().validate()
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
    granularity: SerializableOptional[str] = None
    time_offsets: List[str] = field(default_factory=list)
    post_processing: List[Any] = field(default_factory=list)

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
    queries: List[TableQueryObject] = object_field(cls=TableQueryObject, default_factory=list)

    def validate(self):
        super().validate()
        # junta todas as métricas dos queries numa lista
        query_metrics = [qm for q in self.queries for qm in q.metrics]
        # filtra as métricas do form_data que não aparecem em query_metrics
        missing = [fm for fm in self.form_data.metrics if fm not in query_metrics]
        if missing:
            raise ValidationError(
                message=f'These metrics from form_data are missing in queries.metrics: {missing}',
                solution="Use add_simple_metric ou add_custom_metric para garantir integridade."
            )

    def _default_query_object_class(self) -> type[Query]:
        return TableQueryObject


@dataclass
class TableChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    params: TableOption = object_field(cls=TableOption, default_factory=TableOption)
    query_context: TableQueryContext = object_field(cls=TableQueryContext, default_factory=TableQueryContext)

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
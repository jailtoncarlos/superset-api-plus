"""Charts."""
from dataclasses import dataclass, field, replace
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import AdhocMetricColumn, Metric, OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import ColumnConfig, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import (
    ChartType,
    ComparisonColorScheme,
    ComparisonType,
    DateFormatType,
    MetricType,
    PercentMetricCalculation,
    QueryModeType,
    ResultFormat,
    ResultType,
    TimeGrain,
)
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class TableOptionBase(Option):
    # Dimensions are optional in the UI (a table in raw mode or with metrics only, mixed series, pivot rows).
    _require_groupby: ClassVar[bool] = False
    conditional_formatting: SerializableOptional[list] = field(default=None)
    temporal_columns_lookup: SerializableOptional[dict] = field(default=None)
    annotation_layers: SerializableOptional[list] = field(default=None)


@dataclass
class TableOption(TableOptionBase):
    row_limit: SerializableOptional[int] = 10000
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    order_desc: SerializableOptional[bool] = True
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    comparison_type: SerializableOptional[ComparisonType] = field(default_factory=lambda: ComparisonType.VALUES)
    percent_metric_calculation: SerializableOptional[PercentMetricCalculation] = field(
        default_factory=lambda: PercentMetricCalculation.ROW_LIMIT)
    query_mode: QueryModeType = field(default_factory=lambda: QueryModeType.AGGREGATE)

    order_by_cols: list = field(default_factory=list)

    server_pagination: SerializableOptional[bool] = False
    server_page_length: SerializableOptional[int] = 10
    show_totals: SerializableOptional[bool] = False

    table_timestamp_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    page_length: SerializableOptional[int] = field(default=None)
    include_search: SerializableOptional[bool] = field(default=None)
    show_cell_bars: bool = True

    align_pn: SerializableOptional[bool] = field(default=None)
    color_pn: bool = True
    allow_rearrange_columns: SerializableOptional[bool] = field(default=None)

    table_filter: SerializableOptional[bool] = field(default=None)
    granularity_sqla: SerializableOptional[str] = field(default=None)

    column_config: SerializableOptional[dict[str, ColumnConfig]] = object_field(cls=ColumnConfig, dict_right=True,
                                                                               default=None)

    all_columns: SerializableOptional[list] = field(default_factory=list)
    percent_metrics: SerializableOptional[list] = field(default_factory=list)
    allow_render_html: SerializableOptional[bool] = True
    comparison_color_scheme: SerializableOptional[ComparisonColorScheme] = field(default=None)

    timeseries_limit_metric: SerializableOptional[Metric] = object_field(default=None)

    force: SerializableOptional[bool] = field(default=None)
    result_format: SerializableOptional[ResultFormat] = field(default=None)
    result_type: SerializableOptional[ResultType] = field(default=None)

    def __post_init__(self) -> None:
        super().__post_init__()
        # None becomes an empty list; MissingField (absent key, e.g. a table in raw mode) is kept.
        if self.metrics is None:
            self.metrics: list[Metric] = []
        if self.server_page_length == 0:
            self.server_page_length = 10

    def validate(self) -> None:
        super().validate()
        # In raw mode the table lists columns (all_columns) and does not use metrics.
        if str(self.query_mode) == str(QueryModeType.RAW):
            if not self.all_columns:
                raise ValidationError(message='Field all_columns cannot be empty when query_mode is raw.',
                                      solution='Inform the columns to be listed in all_columns.')
        # In aggregate mode Superset accepts only dimensions (distinct values), only
        # metrics, or both; only a table with none of the three is invalid.
        elif not (self.metrics or self.groupby or self.percent_metrics):
            raise ValidationError(message='Fields metrics, groupby and percent_metrics cannot all be empty.',
                                  solution='Use one of the add_simple_metric, add_custom_metric or '
                                           'add_simple_dimension methods.')

    def _add_column_config(self, label:str, column_config:ColumnConfig) -> None:
        if not isinstance(self.column_config, dict):
            self.column_config = {}
        self.column_config[label] = column_config


@dataclass
class TableFormData(TableOption):
    pass


@dataclass
class TableQueryObject(Query):
    granularity: SerializableOptional[str] = None
    time_offsets: list[str] = field(default_factory=list)
    post_processing: list[Any] = field(default_factory=list)



@dataclass
class TableQueryContext(QueryContext):
    form_data: TableFormData = object_field(cls=TableFormData, default_factory=TableFormData)
    queries: list[TableQueryObject] = object_field(cls=TableQueryObject, default_factory=list)

    @staticmethod
    def _table_order(automatic_order: OrderBy) -> OrderBy:
        # In the table the default direction is descending: invert the request on a copy, without changing
        # the caller's OrderBy (which may be the default value shared between calls).
        if not automatic_order:
            return automatic_order
        return replace(automatic_order, sort_ascending=not automatic_order.sort_ascending)

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy) -> None:
        super()._add_simple_metric(metric, self._table_order(automatic_order))

    def _add_custom_metric(self, label: str,
                           automatic_order: OrderBy,
                           column: AdhocMetricColumn | None = None,
                           sql_expression: str | None = None,
                           aggregate: MetricType | None = None) -> None:
        super()._add_custom_metric(label, self._table_order(automatic_order), column, sql_expression, aggregate)

    def validate(self) -> None:
        super().validate()
        # gather all query metrics into one list
        query_metrics = [qm for q in self.queries if isinstance(q.metrics, list) for qm in q.metrics]
        # keep the form_data metrics that do not appear in query_metrics (absent in raw mode)
        form_data_metrics = self.form_data.metrics if isinstance(self.form_data, SerializableModel) else []
        if not isinstance(form_data_metrics, list):
            form_data_metrics = []
        missing = [fm for fm in form_data_metrics if fm not in query_metrics]
        if missing:
            raise ValidationError(
                message=f'These metrics from form_data are missing in queries.metrics: {missing}',
                solution="Use add_simple_metric or add_custom_metric to ensure integrity."
            )

    def _default_query_object_class(self) -> type[Query]:
        return TableQueryObject


@dataclass
class TableChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.TABLE
    viz_type: ChartType = field(default_factory=lambda: ChartType.TABLE)
    params: TableOption = object_field(cls=TableOption, default_factory=TableOption)
    query_context: TableQueryContext = object_field(cls=TableQueryContext, default_factory=TableQueryContext)

    def add_simple_metric(self, metric: MetricType,
                          automatic_order: OrderBy = OrderBy(),
                          column_config: ColumnConfig | None = None) -> None:
        super().add_simple_metric(metric, automatic_order)
        if column_config:
            self.params._add_column_config(str(metric), column_config)
            self.query_context.form_data._add_column_config(str(metric), column_config)


    def add_custom_metric(self, label: str,
                            automatic_order: OrderBy = OrderBy(),
                            column: AdhocMetricColumn | None = None,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None,
                            column_config: ColumnConfig | None = None) -> None:
        super().add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        if column_config:
            self.params._add_column_config(label, column_config)
            self.query_context.form_data._add_column_config(label, column_config)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TableOption

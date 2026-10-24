"""Charts."""
import warnings
from dataclasses import dataclass, field
from typing import Any

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import AdhocColumn, Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import (
    ChartType,
    ComparisonType,
    ContributionType,
    DateFormatType,
    LabelRotation,
    NumberFormatType,
    Orientation,
    SortSeriesType,
    StackStylyType,
    TimeGrain,
    TitlepositionType,
)
from supersetapiplus.typing import SerializableOptional


@dataclass
class TimeSeriesBarOption(ChartVisualOptionsMixin, Option):
    """Bar chart params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)

    # X axis: a column name or an AdhocColumn; absent until set (the UI proposes the dataset's time column).
    x_axis: SerializableOptional[QueryFormColumn] = object_field(default=None)

    x_axis_sort: SerializableOptional[bool] = field(default=None)
    x_axis_sort_asc: SerializableOptional[bool] = True
    x_axis_sort_series: SerializableOptional[SortSeriesType] = field(default=None)
    x_axis_sort_series_ascending: SerializableOptional[bool] = field(default=None)

    contributionMode: SerializableOptional[ContributionType] = field(default=None)
    row_limit: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    comparison_type: SerializableOptional[ComparisonType] = field(default_factory=lambda: ComparisonType.VALUES)
    group_others_when_limit_reached: SerializableOptional[bool] = False
    truncate_metric: bool = True
    annotation_layers: list = field(default_factory=list)
    forecastEnabled: SerializableOptional[bool] = False
    forecastPeriods: SerializableOptional[int] = 10
    forecastInterval: SerializableOptional[float] = 0.8
    orientation: Orientation = field(default_factory=lambda: Orientation.VERTICAL)

    x_axis_title: SerializableOptional[str] = field(default=None)
    x_axis_title_margin: int = 0
    y_axis_title: SerializableOptional[str] = field(default=None)
    y_axis_title_margin: int = 15
    y_axis_title_position: TitlepositionType = field(default_factory=lambda: TitlepositionType.LEFT)
    x_axis_time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: SerializableOptional[LabelRotation] = field(default=None)

    sort_series_type: SortSeriesType = field(default_factory=lambda: SortSeriesType.SUM)
    sort_series_ascending: SerializableOptional[bool] = field(default=None)
    show_value: SerializableOptional[bool] = field(default=None)
    stack: SerializableOptional[StackStylyType] = field(default=None)
    only_total: bool = True
    percentage_threshold: SerializableOptional[int] = field(default=None)

    logAxis: SerializableOptional[bool] = field(default=None)

    minorSplitLine: SerializableOptional[bool] = field(default=None)
    truncateYAxis: SerializableOptional[bool] = field(default=None)

    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    y_axis_bounds: list[float | None] = field(default_factory=lambda: [None, None])
    rich_tooltip: bool = True
    tooltipTimeFormat: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    show_empty_columns: bool = True
    truncateXAxis: bool = True
    showTooltipTotal: SerializableOptional[bool] = field(default=None)
    showTooltipPercentage: SerializableOptional[bool] = field(default=None)

    xAxisForceCategorical: SerializableOptional[bool] = field(default=None)
    tooltipSortByMetric: SerializableOptional[bool] = field(default=None)

    def validate(self):
        # groupby is not required
        self._require_groupby: bool = False
        super().validate()

    def __post_init__(self):
        super().__post_init__()

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True):
        """X axis column (a column name or an AdhocColumn); optionally sorts the axis by a series aggregate."""
        self.x_axis = column
        if sort_series_by is not None:
            self.x_axis_sort_series = sort_series_by
            self.x_axis_sort_series_ascending = sort_ascending

    def y_axis(self, label: str,
               sql_expression: str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):
        """Deprecated: it sets the X axis (the bar categories); use set_x_axis."""
        warnings.warn("TimeSeriesBarOption.y_axis sets the X axis and is deprecated; use set_x_axis.",
                      DeprecationWarning, stacklevel=2)
        column = AdhocColumn(label=label, sqlExpression=sql_expression or label, hasCustomLabel=True)
        self.set_x_axis(column, sort_series_by, sort_ascending)


@dataclass()
class TimeSeriesBarFormData(TimeSeriesBarOption):
    series_columns: SerializableOptional[list] = field(default=None)



@dataclass
class TimeSeriesBarQueryObject(Query):
    series_columns: SerializableOptional[list] = field(default_factory=list)
    time_offsets: list[str] = field(default_factory=list)
    post_processing: list[Any] = field(default_factory=list)


@dataclass
class TimeSeriesBarQueryContext(QueryContext):
    form_data: TimeSeriesBarFormData = object_field(cls=TimeSeriesBarFormData, default_factory=TimeSeriesBarFormData)
    queries: list[TimeSeriesBarQueryObject] = object_field(cls=TimeSeriesBarQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TimeSeriesBarQueryObject


@dataclass
class EchartsTimeseriesBarChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    params: TimeSeriesBarOption = object_field(
        cls=TimeSeriesBarOption, default_factory=TimeSeriesBarOption)
    query_context: TimeSeriesBarQueryContext = object_field(
        cls=TimeSeriesBarQueryContext,  default_factory=TimeSeriesBarQueryContext)

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True):
        self.params.set_x_axis(column, sort_series_by, sort_ascending)
        self.query_context.form_data.set_x_axis(column, sort_series_by, sort_ascending)

    def y_axis(self, label: str,
               sql_expression: str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):
        """Deprecated: it sets the X axis (the bar categories); use set_x_axis."""
        warnings.warn("EchartsTimeseriesBarChart.y_axis sets the X axis and is deprecated; use set_x_axis.",
                      DeprecationWarning, stacklevel=2)
        column = AdhocColumn(label=label, sqlExpression=sql_expression or label, hasCustomLabel=True)
        self.set_x_axis(column, sort_series_by, sort_ascending)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TimeSeriesBarOption

    # def add_custom_metric(self, label: str,
    #                       automatic_order: OrderBy = OrderBy(),
    #                       column: AdhocMetricColumn = None,
    #                       sql_expression: str = None,
    #                       aggregate: MetricType = None):
    #     if column:
    #         column.id = self.id
    #     self.params._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
    #     self.query_context._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)

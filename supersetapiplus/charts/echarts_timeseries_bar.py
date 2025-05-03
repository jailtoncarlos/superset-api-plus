"""Charts."""
from dataclasses import dataclass, field
from typing import List

from supersetapiplus.base.base import default_string, object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import AdhocMetric, CurrencyFormat, QuerySerializableModel
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, LegendOrientationType, LegendType, DateFormatType, \
    NumberFormatType, TimeGrain, Orientation, ContributionType, SortSeriesType, StackStylyType, \
    TitlepositionType, LabelRotation, ComparisonType, FilterExpressionType
from supersetapiplus.typing import SerializableOptional


@dataclass
class TimeSeriesBarOption(Option):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    color_scheme: str = default_string(default='supersetColors')

    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)

    x_axis: AdhocMetric = object_field(cls=AdhocMetric, default_factory=AdhocMetric)
    x_axis_sort_asc: bool = True

    x_axis_sort_series: SortSeriesType = field(default_factory=lambda: SortSeriesType.NAME)
    x_axis_sort_series_ascending: bool = True

    contributionMode: ContributionType = field(default_factory=lambda: ContributionType.ROW)
    order_desc: bool = True
    row_limit: int = 1000
    truncate_metric: bool = True
    comparison_type: ComparisonType = field(default_factory=lambda: ComparisonType.VALUES)
    annotation_layers: List = field(default_factory=list)
    forecastPeriods: int = 10
    forecastInterval: float = 0.8
    orientation: Orientation = field(default_factory=lambda: Orientation.HORIZONTAL)
    x_axis_title: str = default_string(default=' ')
    x_axis_title_margin: int = 30
    y_axis_title: str = default_string(default='')
    y_axis_title_margin: int = 30
    y_axis_title_position: TitlepositionType = field(default_factory=lambda: TitlepositionType.LEFT)
    sort_series_type: SortSeriesType = field(default_factory=lambda: SortSeriesType.NAME)
    sort_series_ascending: bool = True
    show_value: bool = False
    stack: StackStylyType = field(default_factory=lambda: StackStylyType.STACK)
    only_total: bool = True
    percentage_threshold: int = 0
    show_legend: bool = True
    legendType: LegendType = field(default_factory=lambda: LegendType.SCROLL)
    legendOrientation: LegendOrientationType = field(default_factory=lambda: LegendOrientationType.BOTTOM)
    legendMargin: int = 10
    x_axis_time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: LabelRotation = field(default_factory=lambda: LabelRotation.ZERO)
    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default_factory=CurrencyFormat)
    logAxis: bool = False
    minorSplitLine: bool = False
    truncateYAxis: bool = False
    y_axis_bounds: tuple[int, int] = field(default_factory=dict)
    rich_tooltip: bool = True
    tooltipTimeFormat: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    # extra_form_data: {}
    # dashboards: [20]
    # force: bool = False
    # result_format: str = 'json'
    # result_type: str = 'full'

    def __post_init__(self):
        super().__post_init__()

    def y_axis(self, label: str,
               sql_expression: str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):

        expression_type = FilterExpressionType.SIMPLE
        if sql_expression:
            expression_type = FilterExpressionType.CUSTOM_SQL

        _metric = {
            "label": label,
            "sqlExpression": sql_expression,
            'expressionType': expression_type,
        }
        self.x_axis = AdhocMetric(**_metric)
        self.x_axis_sort_series = sort_series_by
        self.x_axis_sort_series_ascending = sort_ascending


@dataclass
class TimeSeriesBarFormData(TimeSeriesBarOption):
    ...


@dataclass
class TimeSeriesBarQueryObject(QuerySerializableModel):
    ...


@dataclass
class TimeSeriesBarQueryContext(QueryContext):
    queries: List[TimeSeriesBarQueryObject] = object_field(cls=TimeSeriesBarQueryObject, default_factory=list)
    form_data: TimeSeriesBarFormData = object_field(cls=TimeSeriesBarFormData, default_factory=TimeSeriesBarFormData)

    def _default_query_object_class(self) -> type[QuerySerializableModel]:
        return TimeSeriesBarQueryObject


@dataclass
class EchartsTimeseriesBarChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    params: TimeSeriesBarOption = object_field(cls=TimeSeriesBarOption, default_factory=TimeSeriesBarOption)
    query_context: TimeSeriesBarQueryContext = object_field(cls=TimeSeriesBarQueryContext,
                                                           default_factory=TimeSeriesBarQueryContext)

    def y_axis(self, label: str,
               sql_expression: str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):
        self.params.y_axis(label, sql_expression, sort_ascending, sort_series_by)

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
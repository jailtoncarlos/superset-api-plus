"""Charts."""
from dataclasses import dataclass, field
from typing import List, Dict

from supersetapiplus.base.base import default_string, ObjectField
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import MetricsMixin, AdhocMetricColumn, AdhocMetric, CurrencyFormat, OrderBy, \
    QueryObject
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, LegendOrientationType, LegendType, DateFormatType, \
    NumberFormatType, TimeGrain, Orientation, ContributionType, SortSeriesType, StackStylyType, \
    TitlepositionType, LabelRotation, ComparisonType, MetricType, FilterExpressionType
from supersetapiplus.typing import Optional


@dataclass
class TimeSeriesBarOption(Option, MetricsMixin):
    viz_type: ChartType = ChartType.TIMESERIES_BAR
    color_scheme: str = default_string(default='supersetColors')

    time_grain_sqla: Optional[TimeGrain] = TimeGrain.DAY

    x_axis: AdhocMetric = ObjectField(cls=AdhocMetric, default_factory=AdhocMetric)
    x_axis_sort_asc: bool = True
    # Y-AXIS SORT BY
    x_axis_sort_series: SortSeriesType = SortSeriesType.NAME
    # Y-AXIS SORT ASCENDING
    x_axis_sort_series_ascending: bool = True

    contributionMode: ContributionType = ContributionType.ROW
    order_desc: bool = True
    row_limit: int = 1000
    truncate_metric: bool = True
    comparison_type: ComparisonType = ComparisonType.VALUES
    annotation_layers: List = field(default_factory=list)
    forecastPeriods: int = 10
    forecastInterval: float = 0.8
    orientation: Orientation = Orientation.HORIZONTAL
    x_axis_title: str = default_string(default=' ')
    x_axis_title_margin: int = 30
    y_axis_title: str = default_string(default='')
    y_axis_title_margin: int = 30
    y_axis_title_position: TitlepositionType = TitlepositionType.LEFT
    sort_series_type: SortSeriesType = SortSeriesType.NAME
    sort_series_ascending: bool = True
    show_value: bool = False
    stack: StackStylyType = StackStylyType.STACK
    only_total: bool = True
    percentage_threshold: int = 0
    show_legend: bool = True
    legendType: LegendType = LegendType.SCROLL
    legendOrientation: LegendOrientationType = LegendOrientationType.BOTTOM
    legendMargin: int = 10
    x_axis_time_format: DateFormatType = DateFormatType.SMART_DATE
    xAxisLabelRotation: LabelRotation = LabelRotation.ZERO
    y_axis_format: NumberFormatType = NumberFormatType.SMART_NUMBER
    currency_format: Optional[CurrencyFormat] = ObjectField(cls=CurrencyFormat, default_factory=CurrencyFormat)
    logAxis: bool = False
    minorSplitLine: bool = False
    truncateYAxis: bool = False
    y_axis_bounds: tuple[int, int] = field(default_factory=dict)
    rich_tooltip: bool = True
    tooltipTimeFormat: DateFormatType = DateFormatType.SMART_DATE

    # extra_form_data: {}
    # dashboards: [20]
    # force: bool = False
    # result_format: str = 'json'
    # result_type: str = 'full'

    def __post_init__(self):
        super().__post_init__()

    def y_axis(self, label:str,
               sql_expression:str = None,
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
    pass


class TimeSeriesBarQueryObject(QueryObject):
    # columns: Optional[List[Metric]] = ObjectField(cls=AdhocMetric, default_factory=list)
    def y_axis(self, label:str,
               sql_expression:str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):
        _metric = {
            "label": label,
            "sqlExpression": sql_expression,
            'expressionType': expression_type,
        }
        self.x_axis = AdhocMetric(**_metric)
@dataclass
class TimeSeriesBarQueryContext(QueryContext):
    queries: List[TimeSeriesBarQueryObject] = ObjectField(cls=TimeSeriesBarQueryObject, default_factory=list)
    form_data: TimeSeriesBarFormData = ObjectField(cls=TimeSeriesBarFormData, default_factory=TimeSeriesBarFormData)

    def _get_query_object_class(self):
        raise NotImplementedError()


@dataclass
class Echarts_timeseries_barChart(Chart):
    viz_type: ChartType = ChartType.TIMESERIES_BAR
    params: TimeSeriesBarOption =  ObjectField(cls=TimeSeriesBarOption, default_factory=TimeSeriesBarOption)
    query_context: TimeSeriesBarQueryContext =  ObjectField(cls=TimeSeriesBarQueryContext, default_factory=TimeSeriesBarQueryContext)

    def y_axis(self, label:str,
               sql_expression:str = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME):
        self.params.y_axis(label, sql_expression, sort_ascending, sort_series_by)

    # def add_custom_metric(self, label: str,
    #                       automatic_order: OrderBy = OrderBy(),
    #                       column: AdhocMetricColumn = None,
    #                       sql_expression: str = None,
    #                       aggregate: MetricType = None):
    #     if column:
    #         column.id = self.id
    #     self.params._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
    #     self.query_context._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)



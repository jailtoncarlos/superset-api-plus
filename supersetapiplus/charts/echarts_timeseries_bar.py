"""Charts."""
from dataclasses import dataclass, field
from typing import List, Any

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option, ChartVisualOptionsMixin
from supersetapiplus.charts.queries import AdhocMetric, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, \
    NumberFormatType, Orientation, ContributionType, SortSeriesType, StackStylyType, \
    TitlepositionType, LabelRotation, FilterExpressionType
from supersetapiplus.typing import SerializableOptional


@dataclass
class TimeSeriesBarOption(ChartVisualOptionsMixin, Option):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)

    x_axis: AdhocMetric = object_field(cls=AdhocMetric, default_factory=AdhocMetric)

    x_axis_sort: SerializableOptional[bool] = field(default=None)
    x_axis_sort_asc: SerializableOptional[bool] = field(default=None)
    x_axis_sort_series: SerializableOptional[SortSeriesType] = field(default=None)
    x_axis_sort_series_ascending: SerializableOptional[bool] = field(default=None)

    contributionMode: SerializableOptional[ContributionType] = field(default=None)
    row_limit: int = 1000
    truncate_metric: bool = True
    annotation_layers: List = field(default_factory=list)
    forecastPeriods: SerializableOptional[int] = field(default=None)
    forecastInterval: SerializableOptional[float] = field(default=None)
    orientation: Orientation = field(default_factory=lambda: Orientation.HORIZONTAL)

    x_axis_title: SerializableOptional[str] = field(default=None)
    x_axis_title_margin: int = 30
    y_axis_title: SerializableOptional[str] = field(default=None)
    y_axis_title_margin: int = 30
    y_axis_title_position: TitlepositionType = field(default_factory=lambda: TitlepositionType.LEFT)
    x_axis_time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: SerializableOptional[LabelRotation] = field(default=None)

    sort_series_type: SortSeriesType = field(default_factory=lambda: SortSeriesType.NAME)
    sort_series_ascending: SerializableOptional[bool] = field(default=None)
    show_value: SerializableOptional[bool] = field(default=None)
    stack: SerializableOptional[StackStylyType] = field(default=None)
    only_total: bool = True
    percentage_threshold: SerializableOptional[int] = field(default=None)

    logAxis: SerializableOptional[bool] = field(default=None)

    minorSplitLine: SerializableOptional[bool] = field(default=None)
    truncateYAxis: SerializableOptional[bool] = field(default=None)

    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    y_axis_bounds: tuple[int, int] = field(default_factory=dict)
    rich_tooltip: bool = True
    tooltipTimeFormat: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    show_empty_columns: bool = True
    truncateXAxis: bool = True
    showTooltipTotal: SerializableOptional[bool] = field(default=None)
    showTooltipPercentage: SerializableOptional[bool] = field(default=None)

    xAxisForceCategorical: SerializableOptional[bool] = field(default=None)
    tooltipSortByMetric: SerializableOptional[bool] = field(default=None)

    def validate(self):
        # desativa a obrigatoriedade do groupby
        self._require_groupby: bool = False
        super().validate()

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


@dataclass()
class TimeSeriesBarFormData(TimeSeriesBarOption):
    series_columns: SerializableOptional[List] = field(default=None)



@dataclass
class TimeSeriesBarQueryObject(Query):
    series_columns: SerializableOptional[List] = field(default_factory=list)
    time_offsets: List[str] = field(default_factory=list)
    post_processing: List[Any] = field(default_factory=list)


@dataclass
class TimeSeriesBarQueryContext(QueryContext):
    form_data: TimeSeriesBarFormData = object_field(cls=TimeSeriesBarFormData, default_factory=TimeSeriesBarFormData)
    queries: List[TimeSeriesBarQueryObject] = object_field(cls=TimeSeriesBarQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TimeSeriesBarQueryObject


@dataclass
class EchartsTimeseriesBarChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    params: TimeSeriesBarOption = object_field(
        cls=TimeSeriesBarOption, default_factory=TimeSeriesBarOption)
    query_context: TimeSeriesBarQueryContext = object_field(
        cls=TimeSeriesBarQueryContext,  default_factory=TimeSeriesBarQueryContext)

    def validate(self):
        """
        Verifica se params.x_axis_sort corresponde a um 'label' válido em:
          1) self.params.metrics
          2) cada uma das listas de metrics em self.query_context.queries

        Lança ChartValidationError em caso de inconsistência.
        """
        super().validate()
        x_axis_sort_label = self.params.x_axis_sort


        # # 1) Check in params.metrics
        # if not any(metric.label == x_axis_sort_label for metric in self.params.metrics):
        #     raise ChartValidationError(
        #         message=(
        #             f"x_axis_sort='{x_axis_sort_label}' is invalid: "
        #             "it does not match any metric label in params.metrics."
        #         ),
        #         solution=(
        #             "Ensure that 'params.x_axis_sort' matches one of the "
        #             "'metric.label' entries defined in params.metrics."
        #         )
        #     )
        #
        # # 2) Check in each query.metrics of query_context
        # if not any(
        #         metric.label == x_axis_sort_label
        #         for query in self.query_context.queries
        #         for metric in getattr(query, "metrics", [])
        # ):
        #     raise ChartValidationError(
        #         message=(
        #             f"x_axis_sort='{x_axis_sort_label}' is invalid: "
        #             "it does not match any metric label in query_context.queries."
        #         ),
        #         solution=(
        #             "Verify that 'query_context.queries' contains the specified "
        #             "metric label in its metrics lists."
        #         )
        #     )

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
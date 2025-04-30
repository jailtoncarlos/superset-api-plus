"""Charts."""
from dataclasses import dataclass, field
from typing import List

from supersetapiplus.base.base import default_string, object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Metric, CurrencyFormat, AdhocMetric, QueryObject
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, LabelType, LegendOrientationType, LegendType, DateFormatType, \
    NumberFormatType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import Optional


@dataclass
class PieOption(Option, SingleMetricMixin):
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIE)
    color_scheme: str = default_string(default='supersetColors')
    legendType: LegendType = field(default_factory=lambda: LegendType.SCROLL)
    legendOrientation: LegendOrientationType = field(default_factory=lambda: LegendOrientationType.TOP)
    label_type: LabelType = field(default_factory=lambda: LabelType.CATEGORY_NAME)
    show_legend: bool = True
    show_labels: bool = True
    legendMargin: Optional[str] = ''
    currency_format: Optional[CurrencyFormat] = object_field(cls=CurrencyFormat, default_factory=CurrencyFormat)
    number_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    date_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    donut: Optional[bool] = False
    label_line: Optional[bool] = False
    labels_outside: bool = True
    show_total: Optional[bool] = False
    innerRadius: int = 30
    outerRadius: int = 70
    show_labels_threshold: int = 5
    metric: Metric = object_field(cls=AdhocMetric, default=None)
    sort_by_metric: bool = False


    def __post_init__(self):
        super().__post_init__()
        if self.donut and self.innerRadius != 30:
            self.donut = True
        if self.legendMargin:
            self.show_legend = True
        if self.label_line:
            self.labels_outside = True
            self.show_labels = True
        if self.labels_outside:
            self.show_labels = True

    def validate(self, data: dict):
        super().validate(data)

        if not self.metric:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')

        if hasattr(self.metric, 'column') and (not self.metric.column.column_name or not self.metric.column.type):
            raise ValidationError(message='Fields self.metric.column.column_name and self.metric.column.type cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


@dataclass
class PieFormData(PieOption):
    pass


class PieQueryObject(QueryObject):
    ...



@dataclass
class PieQueryContext(QueryContext):
    form_data: PieFormData = object_field(cls=PieFormData, default_factory=PieFormData)
    queries: List[PieQueryObject] = object_field(cls=QueryObject, default_factory=list)

    def validate(self, data: dict):
        super().validate(data)

        if self.form_data.metric or self.queries:
            equals = False
            for query in self.queries:
                for metric in query.metrics:
                    if self.form_data.metric == metric:
                        equals = True
                        break
            if not equals:
                raise ValidationError(message='The metric definition in formdata is not included in queries.metrics.',
                                      solution="We recommend using one of the Chart class's add_simple_metric or add_custom_metric methods to ensure data integrity.")

        if self.automatic_order and self.automatic_order.automate:
            equals = False
            if self.form_data.metric or self.queries:
                for query in self.queries:
                    for order in query.orderby:
                        if not isinstance(order, tuple):
                            raise ValidationError('Order by must be a tuple.',
                                                  slution="We recommend using one of the Chart class's add_simple_metric or add_custom_metric methods to ensure data integrity.")
                        if self.form_data.metric == order[0]:
                            equals = True
                            break

                if not equals:
                    raise ValidationError(message='The metric definition in formdata is not included in queries.orderby.',
                                          solution="We recommend using one of the Chart class's add_simple_metric or add_custom_metric methods to ensure data integrity.")

    def _default_query_object_class(self) -> type[QueryObject]:
        return PieQueryObject


@dataclass
class PieChart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIE)
    params: PieOption = object_field(cls=PieOption, default_factory=PieOption)
    query_context: PieQueryContext = object_field(cls=PieQueryContext, default_factory=PieQueryContext)

    def validate(self, data: dict):
        super().validate(data)
        if (self.params.metric or self.query_context.form_data.metric) and not (self.params.metric == self.query_context.form_data.metric):
                raise ValidationError(message='The metric definition in self.params.metric not equals self.query_context.form_data.metric.',
                                      solution="We recommend using one of the Chart class's add_simple_metric or add_custom_metric methods to ensure data integrity.")

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PieOption

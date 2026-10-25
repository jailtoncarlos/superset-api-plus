"""Charts."""
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, LabelType, NumberFormatType
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

_SOLUTION_USE_ADD_METRIC = ("We recommend using one of the Chart class's add_simple_metric or add_custom_metric "
                            "methods to ensure data integrity.")


class PieOption(SingleMetricMixin, ChartVisualOptionsMixin, Option):
    viz_type: ChartType = Field(default_factory=lambda: ChartType.PIE)
    row_limit: SerializableOptional[int] = 100
    sort_by_metric: bool = True
    label_type: LabelType = Field(default_factory=lambda: LabelType.CATEGORY_NAME)
    show_labels: bool = True

    number_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    date_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)
    donut: SerializableOptional[bool] = False
    label_line: SerializableOptional[bool] = False
    labels_outside: bool = True
    show_total: SerializableOptional[bool] = False
    innerRadius: int = 30
    outerRadius: int = 70
    show_labels_threshold: int = 5

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self.metric:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')

        column = getattr(self.metric, 'column', None)  # None for a SQL-expression metric
        if column is not None and (not column.column_name or not column.type):
            raise ValidationError(message='Fields self.metric.column.column_name and self.metric.column.type cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


class PieFormData(PieOption):
    pass


class PieQueryObject(Query):
    ...


class PieQueryContext(QueryContext):
    form_data: PieFormData = Field(default_factory=PieFormData)
    queries: list[PieQueryObject] = Field(default_factory=list)

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self.form_data.metric or self.queries:
            self._validate_metric_in_queries()
            if self.automatic_order and self.automatic_order.automate:
                self._validate_metric_orderby()

    def _validate_metric_in_queries(self) -> None:
        metrics = (metric for query in self.queries if isinstance(query.metrics, list) for metric in query.metrics)
        if not any(self.form_data.metric == metric for metric in metrics):
            raise ValidationError(message='The metric definition in formdata is not included in queries.metrics.',
                                  solution=_SOLUTION_USE_ADD_METRIC)

    def _validate_metric_orderby(self) -> None:
        orders = [order for query in self.queries if isinstance(query.orderby, list) for order in query.orderby]
        if any(not isinstance(order, tuple) for order in orders):
            raise ValidationError('Order by must be a tuple.', solution=_SOLUTION_USE_ADD_METRIC)
        if not any(self.form_data.metric == order[0] for order in orders):
            raise ValidationError(message='The metric definition in formdata is not included in queries.orderby.',
                                  solution=_SOLUTION_USE_ADD_METRIC)

    def _default_query_object_class(self) -> type[Query]:
        return PieQueryObject


@dataclass
class PieChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.PIE
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIE)
    params: PieOption = field(default_factory=PieOption)
    query_context: PieQueryContext = field(default_factory=PieQueryContext)

    def validate(self) -> None:
        super().validate()
        if self.query_context is None or not isinstance(self.query_context.form_data, ApiModel):
            return
        form_data_metric = self.query_context.form_data.metric
        if (self.params.metric or form_data_metric) and self.params.metric != form_data_metric:
            raise ValidationError(
                message='The metric definition in self.params.metric not equals self.query_context.form_data.metric.',
                solution=_SOLUTION_USE_ADD_METRIC)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PieOption

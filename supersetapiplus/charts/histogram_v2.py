"""Histogram (histogram_v2, plugin-chart-echarts Histogram, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import AdhocMetricColumn, Metric, OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, MetricType, NumberFormatType
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class HistogramOption(Option):
    """Histogram params: the numeric `column` whose values are binned (set_column) and optional `groupby`
    dimensions (one series each); no metric. Defaults are the ones the UI gives a new chart
    (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.HISTOGRAM_V2)
    column: SerializableOptional[QueryFormColumn] = object_field(default=None)
    # The plugin has no metric control: the bins count the rows.
    metrics: list[Metric] | MissingField = field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    color_scheme: str = default_string(default='supersetColors')
    row_limit: SerializableOptional[int] = 10000
    bins: int = 5
    normalize: bool = False
    cumulative: bool = False
    show_value: bool = False
    show_legend: bool = True
    x_axis_title: str = default_string(default='')
    x_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    y_axis_title: str = default_string(default='')
    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)

    def set_column(self, column: QueryFormColumn) -> None:
        """The numeric column whose values are binned (a column name or an AdhocColumn)."""
        self.column = column

    def validate(self) -> None:
        super().validate()
        if not self._read_from_superset and not self.column:
            raise ValidationError(message='Field column cannot be empty.',
                                  solution='Use set_column with the numeric column to bin.')

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy) -> None:
        raise ValidationError(message='A histogram has no metric: its bins count the rows of the column.',
                              solution='Use set_column with the numeric column to bin.')

    def _add_custom_metric(self, label: str, automatic_order: OrderBy, column: AdhocMetricColumn | None,
                           sql_expression: str | None = None, aggregate: MetricType | str | None = None) -> None:
        self._add_simple_metric(label, automatic_order)


@dataclass
class HistogramFormData(HistogramOption):
    pass


@dataclass
class HistogramQueryObject(Query):
    # No metric, so nothing to order by: the buildQuery sends neither.
    orderby: SerializableOptional[list[Any] | MissingField] = field(default_factory=MissingField)
    post_processing: list[Any] = field(default_factory=list)
    _requires_metrics: ClassVar[bool] = False


@dataclass
class HistogramQueryContext(QueryContext):
    form_data: HistogramFormData = object_field(cls=HistogramFormData, default_factory=HistogramFormData)
    queries: list[HistogramQueryObject] = object_field(cls=HistogramQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return HistogramQueryObject


@dataclass
class HistogramChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.HISTOGRAM_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.HISTOGRAM_V2)
    params: HistogramOption = object_field(cls=HistogramOption, default_factory=HistogramOption)
    query_context: HistogramQueryContext = object_field(cls=HistogramQueryContext,
                                                        default_factory=HistogramQueryContext)

    def set_column(self, column: QueryFormColumn) -> None:
        self.params.set_column(column)
        self.query_context.form_data.set_column(column)
        # The query lists the groupby columns and then the binned column (Histogram buildQuery).
        self.query_context.first_queries._editable_columns().append(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return HistogramOption

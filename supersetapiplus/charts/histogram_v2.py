"""Histogram (histogram_v2, plugin-chart-echarts Histogram, Superset 6.1.0)."""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import AdhocMetricColumn, Metric, OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, MetricType, NumberFormatType
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


class HistogramOption(Option):
    """Histogram params: the numeric `column` whose values are binned (set_column) and optional `groupby`
    dimensions (one series each); no metric. Defaults are the ones the UI gives a new chart
    (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HISTOGRAM_V2)
    column: SerializableOptional[QueryFormColumn] = None
    # The plugin has no metric control: the bins count the rows.
    metrics: list[Metric] | MissingField = Field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    color_scheme: str = 'supersetColors'
    row_limit: SerializableOptional[int] = 10000
    bins: int = 5
    normalize: bool = False
    cumulative: bool = False
    show_value: bool = False
    show_legend: bool = True
    x_axis_title: str = ''
    x_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    y_axis_title: str = ''
    y_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)

    def set_column(self, column: QueryFormColumn) -> None:
        """The numeric column whose values are binned (a column name or an AdhocColumn)."""
        self.column = column

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
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


class HistogramFormData(HistogramOption):
    pass


class HistogramQueryObject(Query):
    # No metric, so nothing to order by: the buildQuery sends neither.
    orderby: SerializableOptional[list[Any] | MissingField] = Field(default_factory=MissingField)
    post_processing: list[Any] = Field(default_factory=list)
    _requires_metrics: ClassVar[bool] = False


class HistogramQueryContext(QueryContext):
    form_data: HistogramFormData = Field(default_factory=HistogramFormData)
    queries: list[HistogramQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return HistogramQueryObject


class HistogramChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.HISTOGRAM_V2
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HISTOGRAM_V2)
    params: HistogramOption = Field(default_factory=HistogramOption)
    query_context: HistogramQueryContext = Field(default_factory=HistogramQueryContext)

    def set_column(self, column: QueryFormColumn) -> None:
        self.params.set_column(column)
        self.query_context.form_data.set_column(column)
        # The query lists the groupby columns and then the binned column (Histogram buildQuery).
        self.query_context.first_queries._editable_columns().append(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return HistogramOption

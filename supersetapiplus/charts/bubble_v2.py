"""Bubble chart (bubble_v2, plugin-chart-echarts Bubble, Superset 6.1.0)."""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import AdhocMetricColumn, Metric, MetricHelper, OrderBy
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option, unbounded
from supersetapiplus.charts.queries import Query, QueryFormColumn, custom_column
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, LabelRotation, MetricType, NumberFormatType
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

_METRIC_FIELDS = ("x", "y", "size")


class BubbleOption(ChartVisualOptionsMixin, Option):
    """Bubble params: one bubble per `entity` value, placed by the `x` and `y` metrics and sized by `size`;
    `series` (optional) colors the bubbles. Defaults are the ones the UI gives a new chart
    (tests/fixtures/ui_defaults_6.1.0).

    The metric methods fill x, y and size in this order and the dimension methods fill entity, then series.
    The fields keep the control order: the query lists the metrics in form_data key order (extractQueryFields).
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.BUBBLE_V2)
    entity: SerializableOptional[QueryFormColumn] = None
    x: SerializableOptional[Metric] = None
    y: SerializableOptional[Metric] = None
    size: SerializableOptional[Metric] = None
    series: SerializableOptional[QueryFormColumn] = None
    # The plugin has neither a groupby nor a metrics control.
    groupby: SerializableOptional[list[Any] | MissingField] = Field(default_factory=MissingField)
    metrics: list[Metric] | MissingField = Field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    row_limit: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    # Largest bubble, in pixels (a free-form select of numbers written as text, e.g. '25').
    max_bubble_size: str = '25'
    opacity: float = 0.6
    tooltipSizeFormat: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    x_axis_label: str = ''
    x_axis_title_margin: int = 15
    xAxisFormat: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    xAxisLabelRotation: LabelRotation = Field(default_factory=lambda: LabelRotation.ZERO)
    logXAxis: SerializableOptional[bool] = None
    truncateXAxis: bool = True
    y_axis_label: str = ''
    y_axis_title_margin: int = 15
    y_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    yAxisLabelRotation: LabelRotation = Field(default_factory=lambda: LabelRotation.ZERO)
    logYAxis: SerializableOptional[bool] = None
    truncateYAxis: bool = False
    y_axis_bounds: list[float | None] = Field(default_factory=unbounded)

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset:
            return
        missing = [name for name in ("entity", *_METRIC_FIELDS) if not getattr(self, name)]
        if missing:
            raise ValidationError(message=f"A bubble chart needs {', '.join(missing)}.",
                                  solution='Add three metrics (x, y, size) and the entity dimension.')

    def _set_metric(self, metric: Metric) -> None:
        free = next((name for name in _METRIC_FIELDS if not getattr(self, name)), None)
        if free is None:
            raise ValidationError(message='A bubble chart has three metrics (x, y and size).',
                                  solution='Set chart.params.x, .y or .size to replace one.')
        setattr(self, free, metric)

    def _add_simple_metric(self, metric: str, automatic_order: OrderBy) -> None:
        MetricHelper.check_metric(metric)
        self._set_metric(metric)

    def _add_custom_metric(self, label: str, automatic_order: OrderBy, column: AdhocMetricColumn | None,
                           sql_expression: str | None = None, aggregate: MetricType | str | None = None) -> None:
        self._set_metric(MetricHelper.get_metric(label, column, sql_expression, aggregate))

    def _set_dimension(self, column: QueryFormColumn) -> None:
        if self.entity and self.series:
            raise ValidationError(message='A bubble chart has two dimensions (entity and series).',
                                  solution='Set chart.params.entity or .series to replace one.')
        if self.entity:
            self.series = column
        else:
            self.entity = column

    def _add_simple_groupby(self, column_name: str) -> None:
        self._set_dimension(column_name)

    def _add_custom_groupby(self, label: str, column: Any = None, sql_expression: str | None = None,
                            aggregate: Any = None) -> None:
        self._set_dimension(custom_column(label, column, sql_expression, aggregate))


class BubbleFormData(BubbleOption):
    pass


class BubbleQueryObject(Query):
    ...


class BubbleQueryContext(QueryContext):
    form_data: BubbleFormData = Field(default_factory=BubbleFormData)
    queries: list[BubbleQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return BubbleQueryObject


class BubbleChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.BUBBLE_V2
    viz_type: ChartType = Field(default_factory=lambda: ChartType.BUBBLE_V2)
    params: BubbleOption = Field(default_factory=BubbleOption)
    query_context: BubbleQueryContext = Field(default_factory=BubbleQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BubbleOption

"""Heatmap (heatmap_v2, plugin-chart-echarts Heatmap, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import (
    ChartType,
    DateFormatType,
    HeatmapLegendType,
    HeatmapNormalizeAcross,
    HeatmapSortAxis,
    LabelRotation,
    NumberFormatType,
    TimeGrain,
)
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class HeatmapOption(SingleMetricMixin, Option):
    """Heatmap params: the `x_axis` column (set_x_axis), one `groupby` column for the Y axis and one `metric`
    colouring the cells; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.HEATMAP_V2)
    x_axis: SerializableOptional[QueryFormColumn] = object_field(default=None)
    _require_groupby: ClassVar[bool] = False  # checked in validate: exactly one Y column
    _sorts_by_metric: ClassVar[bool] = False  # no sort_by_metric control: sort_x_axis / sort_y_axis
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    row_limit: SerializableOptional[int] = 10000
    sort_x_axis: SerializableOptional[HeatmapSortAxis] = None
    sort_y_axis: SerializableOptional[HeatmapSortAxis] = None
    normalize_across: HeatmapNormalizeAcross = field(default_factory=lambda: HeatmapNormalizeAcross.HEATMAP)
    legend_type: HeatmapLegendType = field(default_factory=lambda: HeatmapLegendType.CONTINUOUS)
    linear_color_scheme: str = default_string(default='superset_seq_1')
    # RGBA of the cell borders ({"r", "g", "b", "a"}, ColorPickerControl).
    border_color: dict[str, float] = field(default_factory=lambda: {"a": 1, "b": 0, "g": 0, "r": 0})
    border_width: float = 0
    xscale_interval: int = -1
    yscale_interval: int = -1
    # 'auto' or a number of pixels (free-form select).
    left_margin: str | int = 'auto'
    bottom_margin: str | int = 'auto'
    value_bounds: list[float | None] = field(default_factory=lambda: [None, None])
    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    x_axis_time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: LabelRotation = field(default_factory=lambda: LabelRotation.ZERO)
    show_legend: bool = True
    show_percentage: bool = True
    show_values: bool = False
    normalized: bool = False

    def set_x_axis(self, column: QueryFormColumn) -> None:
        """The X axis column (a column name or an AdhocColumn); `groupby` holds the Y axis column."""
        self.x_axis = column

    def validate(self) -> None:
        super().validate()
        if self._read_from_superset:
            return
        if not self.metric or not self.x_axis:
            raise ValidationError(message='A heatmap needs a metric and an X axis column.',
                                  solution='Use add_simple_metric (or add_custom_metric) and set_x_axis.')
        if not isinstance(self.groupby, list) or len(self.groupby) != 1:
            raise ValidationError(message='A heatmap has exactly one Y axis column (groupby).',
                                  solution='Call add_simple_dimension or add_custom_dimension once.')


@dataclass
class HeatmapFormData(HeatmapOption):
    pass


@dataclass
class HeatmapQueryObject(Query):
    post_processing: list[Any] = field(default_factory=list)


@dataclass
class HeatmapQueryContext(QueryContext):
    form_data: HeatmapFormData = object_field(cls=HeatmapFormData, default_factory=HeatmapFormData)
    queries: list[HeatmapQueryObject] = object_field(cls=HeatmapQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return HeatmapQueryObject


@dataclass
class HeatmapChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.HEATMAP_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.HEATMAP_V2)
    params: HeatmapOption = object_field(cls=HeatmapOption, default_factory=HeatmapOption)
    query_context: HeatmapQueryContext = object_field(cls=HeatmapQueryContext,
                                                      default_factory=HeatmapQueryContext)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return HeatmapOption

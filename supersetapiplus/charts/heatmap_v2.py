"""Heatmap (heatmap_v2, plugin-chart-echarts Heatmap, Superset 6.1.0)."""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option, unbounded
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
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


def _border_color() -> dict[str, float]:
    """RGBA default of the color picker control (the UI default of a new chart)."""
    return {"a": 1, "b": 0, "g": 0, "r": 0}

class HeatmapOption(SingleMetricMixin, Option):
    """Heatmap params: the `x_axis` column (set_x_axis), one `groupby` column for the Y axis and one `metric`
    colouring the cells; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HEATMAP_V2)
    x_axis: SerializableOptional[QueryFormColumn] = None
    _require_groupby: ClassVar[bool] = False  # checked in validate: exactly one Y column
    _sorts_by_metric: ClassVar[bool] = False  # no sort_by_metric control: sort_x_axis / sort_y_axis
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)
    row_limit: SerializableOptional[int] = 10000
    sort_x_axis: SerializableOptional[HeatmapSortAxis] = None
    sort_y_axis: SerializableOptional[HeatmapSortAxis] = None
    normalize_across: HeatmapNormalizeAcross = Field(default_factory=lambda: HeatmapNormalizeAcross.HEATMAP)
    legend_type: HeatmapLegendType = Field(default_factory=lambda: HeatmapLegendType.CONTINUOUS)
    linear_color_scheme: str = 'superset_seq_1'
    # RGBA of the cell borders ({"r", "g", "b", "a"}, ColorPickerControl).
    border_color: dict[str, float] = Field(default_factory=_border_color)
    border_width: float = 0
    xscale_interval: int = -1
    yscale_interval: int = -1
    # 'auto' or a number of pixels (free-form select).
    left_margin: str | int = 'auto'
    bottom_margin: str | int = 'auto'
    value_bounds: list[float | None] = Field(default_factory=unbounded)
    y_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = None
    x_axis_time_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: LabelRotation = Field(default_factory=lambda: LabelRotation.ZERO)
    show_legend: bool = True
    show_percentage: bool = True
    show_values: bool = False
    normalized: bool = False

    def set_x_axis(self, column: QueryFormColumn) -> None:
        """The X axis column (a column name or an AdhocColumn); `groupby` holds the Y axis column."""
        self.x_axis = column

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset:
            return
        if not self.metric or not self.x_axis:
            raise ValidationError(message='A heatmap needs a metric and an X axis column.',
                                  solution='Use add_simple_metric (or add_custom_metric) and set_x_axis.')
        if not isinstance(self.groupby, list) or len(self.groupby) != 1:
            raise ValidationError(message='A heatmap has exactly one Y axis column (groupby).',
                                  solution='Call add_simple_dimension or add_custom_dimension once.')


class HeatmapFormData(HeatmapOption):
    pass


class HeatmapQueryObject(Query):
    post_processing: list[Any] = Field(default_factory=list)


class HeatmapQueryContext(QueryContext):
    form_data: HeatmapFormData = Field(default_factory=HeatmapFormData)
    queries: list[HeatmapQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return HeatmapQueryObject


class HeatmapChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.HEATMAP_V2
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HEATMAP_V2)
    params: HeatmapOption = Field(default_factory=HeatmapOption)
    query_context: HeatmapQueryContext = Field(default_factory=HeatmapQueryContext)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return HeatmapOption

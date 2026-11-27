"""Controls shared by the ECharts timeseries charts (bar, line, area: plugin-chart-echarts Timeseries, Superset 6.1.0).

The three plugins use the same buildQuery (Timeseries/buildQuery.ts) and most of the same controls; each chart
module adds its own (bar: orientation; line: area, markers; area: series style, stack).
"""
import copy
from typing import Any, Protocol

from pydantic import Field

from supersetapiplus.charts.options import unbounded
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.types import (
    AnnotationOpacity,
    AnnotationSourceType,
    AnnotationStyle,
    AnnotationType,
    ComparisonType,
    ContributionType,
    DateFormatType,
    LabelRotation,
    NumberFormatType,
    SortSeriesType,
    StackStyleType,
    TimeGrain,
    TitlePositionType,
)
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


def formula_annotation_layer(name: str, formula: str, style: AnnotationStyle = AnnotationStyle.SOLID,
                             width: float = 1, color: str | None = None,
                             opacity: AnnotationOpacity = AnnotationOpacity.UNDEFINED, show_label: bool = False,
                             show: bool = True) -> dict[str, Any]:
    """A formula annotation layer as the Explore annotation popover saves it (AnnotationLayer.tsx, applyAnnotation,
    Superset 6.1.0): a line drawn over the chart from a mathjs expression of ``x`` (e.g. ``"3000"`` for a
    horizontal reference line, ``"2 * x"``). The frontend draws it; the query sends it unchanged.

    Args:
        name: the layer name, shown in the legend and the tooltip.
        formula: the expression; a constant gives a horizontal line.
        style: line style.
        width: line width in px.
        color: a hex color (``"#ff0000"``); None for the automatic color of the color scheme.
        opacity: line opacity (the empty value is opaque).
        show_label: show the name on the line.
        show: draw the layer (a hidden layer is kept in the params).
    """
    if not name.strip() or not formula.strip():
        raise ValidationError(message="A formula annotation layer needs a name and a formula.",
                              solution="Pass a non-empty name and expression (e.g. '3000' or '2 * x').")
    return {
        "name": name, "annotationType": str(AnnotationType.FORMULA), "sourceType": str(AnnotationSourceType.UNDEFINED),
        "color": color, "opacity": str(opacity), "style": str(style), "width": width, "showMarkers": False,
        "hideLine": False, "overrides": {}, "show": show, "showLabel": show_label, "titleColumn": "",
        "descriptionColumns": [], "timeColumn": "", "intervalEndColumn": "", "value": formula,
    }


class TimeseriesOptionsMixin(ApiModel):
    """Timeseries params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    # X axis: a column name or an AdhocColumn; absent until set (the UI proposes the dataset's time column).
    x_axis: SerializableOptional[QueryFormColumn] = None

    x_axis_sort: SerializableOptional[bool] = None
    x_axis_sort_asc: SerializableOptional[bool] = True
    x_axis_sort_series: SerializableOptional[SortSeriesType] = None
    x_axis_sort_series_ascending: SerializableOptional[bool] = None

    contributionMode: SerializableOptional[ContributionType] = None
    row_limit: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)
    comparison_type: SerializableOptional[ComparisonType] = Field(default_factory=lambda: ComparisonType.VALUES)
    group_others_when_limit_reached: SerializableOptional[bool] = False
    truncate_metric: bool = True
    annotation_layers: list[Any] = Field(default_factory=list)
    forecastEnabled: SerializableOptional[bool] = False
    forecastPeriods: SerializableOptional[int] = 10
    forecastInterval: SerializableOptional[float] = 0.8

    x_axis_title: SerializableOptional[str] = None
    x_axis_title_margin: int = 0
    y_axis_title: SerializableOptional[str] = None
    y_axis_title_margin: int = 0
    y_axis_title_position: TitlePositionType = Field(default_factory=lambda: TitlePositionType.LEFT)
    x_axis_time_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)
    xAxisLabelRotation: SerializableOptional[LabelRotation] = None

    sort_series_type: SortSeriesType = Field(default_factory=lambda: SortSeriesType.SUM)
    sort_series_ascending: SerializableOptional[bool] = None
    show_value: SerializableOptional[bool] = None
    stack: SerializableOptional[StackStyleType] = None
    only_total: bool = True
    percentage_threshold: SerializableOptional[int] = None

    logAxis: SerializableOptional[bool] = None

    minorSplitLine: SerializableOptional[bool] = None
    truncateYAxis: SerializableOptional[bool] = None

    y_axis_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    y_axis_bounds: list[float | None] = Field(default_factory=unbounded)
    rich_tooltip: bool = True
    tooltipTimeFormat: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)

    show_empty_columns: bool = True
    truncateXAxis: bool = True
    showTooltipTotal: SerializableOptional[bool] = None
    showTooltipPercentage: SerializableOptional[bool] = None

    xAxisForceCategorical: SerializableOptional[bool] = None
    tooltipSortByMetric: SerializableOptional[bool] = None

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True) -> None:
        """X axis column (a column name or an AdhocColumn); optionally sorts the axis by a series aggregate."""
        self.x_axis = column
        if sort_series_by is not None:
            self.x_axis_sort_series = sort_series_by
            self.x_axis_sort_series_ascending = sort_ascending

    def add_annotation_layer(self, layer: dict[str, Any]) -> None:
        """Appends an annotation layer (e.g. :func:`formula_annotation_layer`). A layer with the same name is
        replaced: the frontend keys the annotation data and errors by layer name (AnnotationLayerControl), so two
        layers with one name would collide."""
        layers = [item for item in self.annotation_layers
                  if not (isinstance(item, dict) and item.get("name") == layer.get("name"))]
        self.annotation_layers = [*layers, layer]


class TimeseriesQueryObject(Query):
    series_columns: SerializableOptional[list[Any]] = Field(default_factory=list)
    time_offsets: list[str] = Field(default_factory=list)
    post_processing: list[Any] = Field(default_factory=list)


class _TimeseriesChart(Protocol):
    @property
    def params(self) -> TimeseriesOptionsMixin: ...

    @property
    def query_context(self) -> object: ...


class AnnotationLayersChartMixin:
    """Annotation layer builders of the timeseries charts (the annotationsAndLayersControls section of their
    control panels): params and the stored query_context form_data get the same layer."""

    def add_formula_annotation(self: _TimeseriesChart, name: str, formula: str,
                               style: AnnotationStyle = AnnotationStyle.SOLID, width: float = 1,
                               color: str | None = None, opacity: AnnotationOpacity = AnnotationOpacity.UNDEFINED,
                               show_label: bool = False, show: bool = True) -> None:
        """Adds a formula annotation layer, e.g. a reference line (``formula="3000"``) or a control limit; see
        :func:`formula_annotation_layer` for the arguments."""
        layer = formula_annotation_layer(name, formula, style, width, color, opacity, show_label, show)
        self.params.add_annotation_layer(layer)
        form_data = getattr(self.query_context, "form_data", None)
        if isinstance(form_data, TimeseriesOptionsMixin):
            form_data.add_annotation_layer(copy.deepcopy(layer))

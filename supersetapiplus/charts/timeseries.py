"""Controls shared by the ECharts timeseries charts (bar, line, area: plugin-chart-echarts Timeseries, Superset 6.1.0).

The three plugins use the same buildQuery (Timeseries/buildQuery.ts) and most of the same controls; each chart
module adds its own (bar: orientation; line: area, markers; area: series style, stack).
"""
from typing import Any

from pydantic import Field

from supersetapiplus.charts.options import unbounded
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.types import (
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


class TimeseriesQueryObject(Query):
    series_columns: SerializableOptional[list[Any]] = Field(default_factory=list)
    time_offsets: list[str] = Field(default_factory=list)
    post_processing: list[Any] = Field(default_factory=list)

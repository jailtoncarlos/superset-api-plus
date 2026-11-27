"""Scatter plot (echarts_timeseries_scatter, plugin-chart-echarts Timeseries/Regular/Scatter, Superset 6.1.0).

The timeseries chart drawn as points: same query (Timeseries/buildQuery.ts) and controls as the line chart, without
the area and its opacity. Reference lines over the points (e.g. control limits) are formula annotation layers
(:meth:`EchartsTimeseriesScatterChart.add_formula_annotation`).
"""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.timeseries import (
    AnnotationLayersChartMixin,
    TimeseriesOptionsMixin,
    TimeseriesQueryObject,
)
from supersetapiplus.charts.types import ChartType, SortSeriesType
from supersetapiplus.core.typing import SerializableOptional


class TimeseriesScatterOption(TimeseriesOptionsMixin, ChartVisualOptionsMixin, Option):
    """Scatter plot params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `metrics` are the series of points, `x_axis` (set_x_axis) the time or category axis and `groupby` splits each
    metric into one series per value.
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.TIMESERIES_SCATTER)
    _require_groupby: ClassVar[bool] = False

    markerEnabled: bool = False
    markerSize: int = 6
    zoomable: bool = False


class TimeseriesScatterFormData(TimeseriesScatterOption):
    series_columns: SerializableOptional[list[Any]] = None


class TimeseriesScatterQueryObject(TimeseriesQueryObject):
    pass


class TimeseriesScatterQueryContext(QueryContext):
    form_data: TimeseriesScatterFormData = Field(default_factory=TimeseriesScatterFormData)
    queries: list[TimeseriesScatterQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TimeseriesScatterQueryObject


class EchartsTimeseriesScatterChart(AnnotationLayersChartMixin, Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.TIMESERIES_SCATTER
    viz_type: ChartType = Field(default_factory=lambda: ChartType.TIMESERIES_SCATTER)
    params: TimeseriesScatterOption = Field(default_factory=TimeseriesScatterOption)
    query_context: TimeseriesScatterQueryContext = Field(default_factory=TimeseriesScatterQueryContext)

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True) -> None:
        self.params.set_x_axis(column, sort_series_by, sort_ascending)
        form_data = getattr(self.query_context, "form_data", None)  # null when read without a query context
        if isinstance(form_data, TimeseriesOptionsMixin):
            form_data.set_x_axis(column, sort_series_by, sort_ascending)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TimeseriesScatterOption

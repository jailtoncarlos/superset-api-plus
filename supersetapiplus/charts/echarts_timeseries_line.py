"""Line chart (echarts_timeseries_line, plugin-chart-echarts Timeseries/Regular/Line, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.timeseries import TimeseriesOptionsMixin, TimeseriesQueryObject
from supersetapiplus.charts.types import ChartType, SortSeriesType
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.typing import SerializableOptional


@dataclass
class TimeseriesLineOption(TimeseriesOptionsMixin, ChartVisualOptionsMixin, Option):
    """Line chart params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `metrics` are the lines, `x_axis` (set_x_axis) the time or category axis and `groupby` splits each metric
    into one line per value.
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_LINE)
    _require_groupby: ClassVar[bool] = False

    area: bool = False
    opacity: float = 0.2
    markerEnabled: bool = False
    markerSize: int = 6
    zoomable: bool = False


@dataclass
class TimeseriesLineFormData(TimeseriesLineOption):
    series_columns: SerializableOptional[list[Any]] = field(default=None)


@dataclass
class TimeseriesLineQueryObject(TimeseriesQueryObject):
    pass


@dataclass
class TimeseriesLineQueryContext(QueryContext):
    form_data: TimeseriesLineFormData = object_field(cls=TimeseriesLineFormData,
                                                     default_factory=TimeseriesLineFormData)
    queries: list[TimeseriesLineQueryObject] = object_field(cls=TimeseriesLineQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TimeseriesLineQueryObject


@dataclass
class EchartsTimeseriesLineChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.TIMESERIES_LINE
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_LINE)
    params: TimeseriesLineOption = object_field(cls=TimeseriesLineOption, default_factory=TimeseriesLineOption)
    query_context: TimeseriesLineQueryContext = object_field(cls=TimeseriesLineQueryContext,
                                                             default_factory=TimeseriesLineQueryContext)

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True) -> None:
        self.params.set_x_axis(column, sort_series_by, sort_ascending)
        self.query_context.form_data.set_x_axis(column, sort_series_by, sort_ascending)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TimeseriesLineOption

"""Area chart (echarts_area, plugin-chart-echarts Timeseries/Area, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.timeseries import TimeseriesOptionsMixin, TimeseriesQueryObject
from supersetapiplus.charts.types import ChartType, SortSeriesType, TimeseriesSeriesType
from supersetapiplus.core.typing import SerializableOptional


class AreaOption(TimeseriesOptionsMixin, ChartVisualOptionsMixin, Option):
    """Area chart params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    Same query as the line chart; `stack` takes StackStyleType (Expand only here: AreaChartStackControlOptions).
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.AREA)
    _require_groupby: ClassVar[bool] = False

    seriesType: TimeseriesSeriesType = Field(default_factory=lambda: TimeseriesSeriesType.LINE)
    opacity: float = 0.2
    show_extra_controls: bool = False
    markerEnabled: bool = False
    markerSize: int = 6
    zoomable: bool = False


class AreaFormData(AreaOption):
    series_columns: SerializableOptional[list[Any]] = None


class AreaQueryObject(TimeseriesQueryObject):
    pass


class AreaQueryContext(QueryContext):
    form_data: AreaFormData = Field(default_factory=AreaFormData)
    queries: list[AreaQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return AreaQueryObject


@dataclass
class EchartsAreaChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.AREA
    viz_type: ChartType = field(default_factory=lambda: ChartType.AREA)
    params: AreaOption = field(default_factory=AreaOption)
    query_context: AreaQueryContext = field(default_factory=AreaQueryContext)

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True) -> None:
        self.params.set_x_axis(column, sort_series_by, sort_ascending)
        self.query_context.form_data.set_x_axis(column, sort_series_by, sort_ascending)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return AreaOption

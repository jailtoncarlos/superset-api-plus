"""Charts."""
import warnings
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import ChartVisualOptionsMixin, Option
from supersetapiplus.charts.queries import AdhocColumn, Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.timeseries import TimeseriesOptionsMixin, TimeseriesQueryObject
from supersetapiplus.charts.types import ChartType, Orientation, SortSeriesType
from supersetapiplus.core.typing import SerializableOptional


class TimeSeriesBarOption(TimeseriesOptionsMixin, ChartVisualOptionsMixin, Option):
    """Bar chart params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    _require_groupby: ClassVar[bool] = False  # groupby (series breakdown) is optional

    orientation: Orientation = Field(default_factory=lambda: Orientation.VERTICAL)
    y_axis_title_margin: int = 15

    def y_axis(self, label: str,
               sql_expression: str | None = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME) -> None:
        """Deprecated: it sets the X axis (the bar categories); use set_x_axis."""
        warnings.warn("TimeSeriesBarOption.y_axis sets the X axis and is deprecated; use set_x_axis.",
                      DeprecationWarning, stacklevel=2)
        column = AdhocColumn(label=label, sqlExpression=sql_expression or label, hasCustomLabel=True)
        self.set_x_axis(column, sort_series_by, sort_ascending)


class TimeSeriesBarFormData(TimeSeriesBarOption):
    series_columns: SerializableOptional[list[Any]] = None



class TimeSeriesBarQueryObject(TimeseriesQueryObject):
    pass


class TimeSeriesBarQueryContext(QueryContext):
    form_data: TimeSeriesBarFormData = Field(default_factory=TimeSeriesBarFormData)
    queries: list[TimeSeriesBarQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TimeSeriesBarQueryObject


@dataclass
class EchartsTimeseriesBarChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.TIMESERIES_BAR
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    params: TimeSeriesBarOption = field(default_factory=TimeSeriesBarOption)
    query_context: TimeSeriesBarQueryContext = field(default_factory=TimeSeriesBarQueryContext)

    def set_x_axis(self, column: QueryFormColumn, sort_series_by: SortSeriesType | None = None,
                   sort_ascending: bool = True) -> None:
        self.params.set_x_axis(column, sort_series_by, sort_ascending)
        self.query_context.form_data.set_x_axis(column, sort_series_by, sort_ascending)

    def y_axis(self, label: str,
               sql_expression: str | None = None,
               sort_ascending: bool = True,
               sort_series_by: SortSeriesType = SortSeriesType.NAME) -> None:
        """Deprecated: it sets the X axis (the bar categories); use set_x_axis."""
        warnings.warn("EchartsTimeseriesBarChart.y_axis sets the X axis and is deprecated; use set_x_axis.",
                      DeprecationWarning, stacklevel=2)
        column = AdhocColumn(label=label, sqlExpression=sql_expression or label, hasCustomLabel=True)
        self.set_x_axis(column, sort_series_by, sort_ascending)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TimeSeriesBarOption

    # def add_custom_metric(self, label: str,
    #                       automatic_order: OrderBy = OrderBy(),
    #                       column: AdhocMetricColumn = None,
    #                       sql_expression: str = None,
    #                       aggregate: MetricType = None):
    #     if column:
    #         column.id = self.id
    #     self.params._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
    #     self.query_context._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)

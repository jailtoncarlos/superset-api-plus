"""Big Number with Trendline (big_number, plugin-chart-echarts BigNumber/BigNumberWithTrendline, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.big_number_total import BigNumberTotalOption
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import BigNumberAggregation, ChartType, RollingType, TimeGrain
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class BigNumberOption(BigNumberTotalOption):
    """Big Number with Trendline params: one `metric` over the temporal `x_axis` (set_x_axis), no dimensions;
    defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `aggregation` computes the big number from the trendline points; RAW queries the overall value instead
    (a second query without the time column).
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER)
    x_axis: SerializableOptional[QueryFormColumn] = object_field(default=None)
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    aggregation: BigNumberAggregation = field(default_factory=lambda: BigNumberAggregation.LAST_VALUE)
    rolling_type: RollingType = field(default_factory=lambda: RollingType.NONE)
    rolling_periods: SerializableOptional[int] = None
    min_periods: SerializableOptional[int] = None

    # RGBA of the trendline ({"r", "g", "b", "a"}, ColorPickerControl).
    color_picker: dict[str, float] = field(default_factory=lambda: {"a": 1, "b": 135, "g": 122, "r": 0})
    subheader_font_size: float = 0.15
    show_timestamp: bool = False
    show_trend_line: bool = True
    start_y_axis_at_zero: bool = True
    show_x_axis: bool = False
    show_x_axis_min_max_labels: bool = False
    show_y_axis: bool = False
    show_y_axis_min_max_labels: bool = False

    def set_x_axis(self, column: QueryFormColumn) -> None:
        """The temporal column of the trendline (a column name or an AdhocColumn)."""
        self.x_axis = column

    def validate(self) -> None:
        super().validate()
        if not self._read_from_superset and not self.x_axis:
            raise ValidationError(message='Field x_axis cannot be empty.',
                                  solution='Use set_x_axis with the temporal column of the trendline.')


@dataclass
class BigNumberFormData(BigNumberOption):
    pass


@dataclass
class BigNumberQueryObject(Query):
    post_processing: list[Any] = field(default_factory=list)


@dataclass
class BigNumberQueryContext(QueryContext):
    form_data: BigNumberFormData = object_field(cls=BigNumberFormData, default_factory=BigNumberFormData)
    queries: list[BigNumberQueryObject] = object_field(cls=BigNumberQueryObject, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return BigNumberQueryObject


@dataclass
class BigNumberChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.BIG_NUMBER
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER)
    params: BigNumberOption = object_field(cls=BigNumberOption, default_factory=BigNumberOption)
    query_context: BigNumberQueryContext = object_field(cls=BigNumberQueryContext,
                                                        default_factory=BigNumberQueryContext)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BigNumberOption

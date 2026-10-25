"""Big Number with Trendline (big_number, plugin-chart-echarts BigNumber/BigNumberWithTrendline, Superset 6.1.0)."""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.big_number_total import BigNumberTotalOption
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import BigNumberAggregation, ChartType, RollingType, TimeGrain
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


def _trendline_color() -> dict[str, float]:
    """RGBA default of the color picker control (the UI default of a new chart)."""
    return {"a": 1, "b": 135, "g": 122, "r": 0}

class BigNumberOption(BigNumberTotalOption):
    """Big Number with Trendline params: one `metric` over the temporal `x_axis` (set_x_axis), no dimensions;
    defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `aggregation` computes the big number from the trendline points; RAW queries the overall value instead
    (a second query without the time column).
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.BIG_NUMBER)
    x_axis: SerializableOptional[QueryFormColumn] = None
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)
    aggregation: BigNumberAggregation = Field(default_factory=lambda: BigNumberAggregation.LAST_VALUE)
    rolling_type: RollingType = Field(default_factory=lambda: RollingType.NONE)
    rolling_periods: SerializableOptional[int] = None
    min_periods: SerializableOptional[int] = None

    # RGBA of the trendline ({"r", "g", "b", "a"}, ColorPickerControl).
    color_picker: dict[str, float] = Field(default_factory=_trendline_color)
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

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self._read_from_superset and not self.x_axis:
            raise ValidationError(message='Field x_axis cannot be empty.',
                                  solution='Use set_x_axis with the temporal column of the trendline.')


class BigNumberFormData(BigNumberOption):
    pass


class BigNumberQueryObject(Query):
    post_processing: list[Any] = Field(default_factory=list)


class BigNumberQueryContext(QueryContext):
    form_data: BigNumberFormData = Field(default_factory=BigNumberFormData)
    queries: list[BigNumberQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return BigNumberQueryObject


class BigNumberChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.BIG_NUMBER
    viz_type: ChartType = Field(default_factory=lambda: ChartType.BIG_NUMBER)
    params: BigNumberOption = Field(default_factory=BigNumberOption)
    query_context: BigNumberQueryContext = Field(default_factory=BigNumberQueryContext)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BigNumberOption

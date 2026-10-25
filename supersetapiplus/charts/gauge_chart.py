"""Gauge (gauge_chart, plugin-chart-echarts Gauge, Superset 6.1.0)."""
from typing import ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, NumberFormatType
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


class GaugeOption(SingleMetricMixin, Option):
    """Gauge params: one `metric`, optionally split by `groupby` (one pointer per value, up to `row_limit`);
    defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.GAUGE)
    _require_groupby: ClassVar[bool] = False
    color_scheme: str = 'supersetColors'
    row_limit: SerializableOptional[int] = 10
    # Axis range; absent: computed from the data.
    min_val: SerializableOptional[float] = None
    max_val: SerializableOptional[float] = None
    start_angle: float = 225
    end_angle: float = -45
    font_size: int = 15
    number_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = None
    value_formatter: str = '{value}'
    show_pointer: bool = True
    animation: bool = True
    show_axis_tick: bool = False
    show_split_line: bool = False
    split_number: int = 10
    show_progress: bool = True
    overlap: bool = True
    round_cap: bool = False
    # Comma-separated interval bounds ("2,4,5") and the color index of each interval ("1,2,3").
    intervals: str = ''
    interval_color_indices: str = ''

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self.metric and not self._read_from_superset:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


class GaugeFormData(GaugeOption):
    pass


class GaugeQueryObject(Query):
    ...


class GaugeQueryContext(QueryContext):
    form_data: GaugeFormData = Field(default_factory=GaugeFormData)
    queries: list[GaugeQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return GaugeQueryObject


class GaugeChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.GAUGE
    viz_type: ChartType = Field(default_factory=lambda: ChartType.GAUGE)
    params: GaugeOption = Field(default_factory=GaugeOption)
    query_context: GaugeQueryContext = Field(default_factory=GaugeQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return GaugeOption

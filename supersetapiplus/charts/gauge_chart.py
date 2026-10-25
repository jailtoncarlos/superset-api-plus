"""Gauge (gauge_chart, plugin-chart-echarts Gauge, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, NumberFormatType
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class GaugeOption(SingleMetricMixin, Option):
    """Gauge params: one `metric`, optionally split by `groupby` (one pointer per value, up to `row_limit`);
    defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.GAUGE)
    _require_groupby: ClassVar[bool] = False
    color_scheme: str = default_string(default='supersetColors')
    row_limit: SerializableOptional[int] = 10
    # Axis range; absent: computed from the data.
    min_val: SerializableOptional[float] = None
    max_val: SerializableOptional[float] = None
    start_angle: float = 225
    end_angle: float = -45
    font_size: int = 15
    number_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    value_formatter: str = default_string(default='{value}')
    show_pointer: bool = True
    animation: bool = True
    show_axis_tick: bool = False
    show_split_line: bool = False
    split_number: int = 10
    show_progress: bool = True
    overlap: bool = True
    round_cap: bool = False
    # Comma-separated interval bounds ("2,4,5") and the color index of each interval ("1,2,3").
    intervals: str = default_string(default='')
    interval_color_indices: str = default_string(default='')

    def validate(self) -> None:
        super().validate()
        if not self.metric and not self._read_from_superset:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


@dataclass
class GaugeFormData(GaugeOption):
    pass


class GaugeQueryObject(Query):
    ...


@dataclass
class GaugeQueryContext(QueryContext):
    form_data: GaugeFormData = object_field(cls=GaugeFormData, default_factory=GaugeFormData)
    queries: list[GaugeQueryObject] = object_field(cls=Query, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return GaugeQueryObject


@dataclass
class GaugeChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.GAUGE
    viz_type: ChartType = field(default_factory=lambda: ChartType.GAUGE)
    params: GaugeOption = object_field(cls=GaugeOption, default_factory=GaugeOption)
    query_context: GaugeQueryContext = object_field(cls=GaugeQueryContext, default_factory=GaugeQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return GaugeOption

"""Funnel (funnel, plugin-chart-echarts Funnel, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import (
    ChartType,
    FunnelLabelType,
    FunnelPercentCalcType,
    LegendOrientationType,
    NumberFormatType,
)
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class FunnelOption(SingleMetricMixin, Option):
    """Funnel params: one `metric` and the `groupby` dimensions (the steps); defaults are the ones the UI gives
    a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.FUNNEL)
    _require_groupby: ClassVar[bool] = False  # without a dimension the funnel has a single step
    color_scheme: str = default_string(default='supersetColors')
    row_limit: SerializableOptional[int] = 10
    sort_by_metric: bool = True
    percent_calculation_type: FunnelPercentCalcType = field(
        default_factory=lambda: FunnelPercentCalcType.FIRST_STEP)
    show_legend: bool = True
    legendOrientation: LegendOrientationType = field(default_factory=lambda: LegendOrientationType.TOP)
    label_type: FunnelLabelType = field(default_factory=lambda: FunnelLabelType.KEY)
    tooltip_label_type: FunnelLabelType = field(default_factory=lambda: FunnelLabelType.KEY_VALUE_PERCENT)
    number_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    show_labels: bool = True
    show_tooltip_labels: bool = True

    def validate(self) -> None:
        super().validate()
        if not self.metric and not self._read_from_superset:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


@dataclass
class FunnelFormData(FunnelOption):
    pass


class FunnelQueryObject(Query):
    ...


@dataclass
class FunnelQueryContext(QueryContext):
    form_data: FunnelFormData = object_field(cls=FunnelFormData, default_factory=FunnelFormData)
    queries: list[FunnelQueryObject] = object_field(cls=Query, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return FunnelQueryObject


@dataclass
class FunnelChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.FUNNEL
    viz_type: ChartType = field(default_factory=lambda: ChartType.FUNNEL)
    params: FunnelOption = object_field(cls=FunnelOption, default_factory=FunnelOption)
    query_context: FunnelQueryContext = object_field(cls=FunnelQueryContext, default_factory=FunnelQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return FunnelOption

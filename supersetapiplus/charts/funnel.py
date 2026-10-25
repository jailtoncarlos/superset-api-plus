"""Funnel (funnel, plugin-chart-echarts Funnel, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import Field

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
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


class FunnelOption(SingleMetricMixin, Option):
    """Funnel params: one `metric` and the `groupby` dimensions (the steps); defaults are the ones the UI gives
    a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.FUNNEL)
    _require_groupby: ClassVar[bool] = False  # without a dimension the funnel has a single step
    color_scheme: str = 'supersetColors'
    row_limit: SerializableOptional[int] = 10
    sort_by_metric: bool = True
    percent_calculation_type: FunnelPercentCalcType = Field(default_factory=lambda: FunnelPercentCalcType.FIRST_STEP)
    show_legend: bool = True
    legendOrientation: LegendOrientationType = Field(default_factory=lambda: LegendOrientationType.TOP)
    label_type: FunnelLabelType = Field(default_factory=lambda: FunnelLabelType.KEY)
    tooltip_label_type: FunnelLabelType = Field(default_factory=lambda: FunnelLabelType.KEY_VALUE_PERCENT)
    number_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = None
    show_labels: bool = True
    show_tooltip_labels: bool = True

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self.metric and not self._read_from_superset:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


class FunnelFormData(FunnelOption):
    pass


class FunnelQueryObject(Query):
    ...


class FunnelQueryContext(QueryContext):
    form_data: FunnelFormData = Field(default_factory=FunnelFormData)
    queries: list[FunnelQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return FunnelQueryObject


@dataclass
class FunnelChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.FUNNEL
    viz_type: ChartType = field(default_factory=lambda: ChartType.FUNNEL)
    params: FunnelOption = field(default_factory=FunnelOption)
    query_context: FunnelQueryContext = field(default_factory=FunnelQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return FunnelOption

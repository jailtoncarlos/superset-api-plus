"""Sunburst (sunburst_v2, plugin-chart-echarts Sunburst, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import Metric, SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query, QueryFormColumn, custom_column
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, NumberFormatType, SunburstLabelType
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


class SunburstOption(SingleMetricMixin, Option):
    """Sunburst params: one `metric` sizes the arcs and the `columns` hierarchy nests them (the dimension
    methods append to it); defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.SUNBURST_V2)
    columns: list[QueryFormColumn] = Field(default_factory=list)
    # The plugin has no groupby control: the dimensions are `columns`.
    groupby: SerializableOptional[list[Any] | MissingField] = Field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    # Optional: colors the arcs by its ratio to `metric` (categorical colors when absent).
    secondary_metric: SerializableOptional[Metric] = None
    color_scheme: str = 'supersetColors'
    linear_color_scheme: str = 'superset_seq_1'
    row_limit: SerializableOptional[int] = 10000
    show_labels: bool = False
    show_labels_threshold: float = 5
    show_total: bool = False
    label_type: SunburstLabelType = Field(default_factory=lambda: SunburstLabelType.KEY)
    number_format: NumberFormatType = Field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = None
    date_format: DateFormatType = Field(default_factory=lambda: DateFormatType.SMART_DATE)

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset:
            return
        if not self.metric:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')
        if not self.columns:
            raise ValidationError(message='A sunburst needs at least one column in its hierarchy.',
                                  solution='Use add_simple_dimension or add_custom_dimension.')

    def _add_simple_groupby(self, column_name: str) -> None:
        self.columns.append(column_name)

    def _add_custom_groupby(self, label: str, column: Any = None, sql_expression: str | None = None,
                            aggregate: Any = None) -> None:
        self.columns.append(custom_column(label, column, sql_expression, aggregate))


class SunburstFormData(SunburstOption):
    pass


class SunburstQueryObject(Query):
    ...


class SunburstQueryContext(QueryContext):
    form_data: SunburstFormData = Field(default_factory=SunburstFormData)
    queries: list[SunburstQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return SunburstQueryObject


@dataclass
class SunburstChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.SUNBURST_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.SUNBURST_V2)
    params: SunburstOption = field(default_factory=SunburstOption)
    query_context: SunburstQueryContext = field(default_factory=SunburstQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return SunburstOption

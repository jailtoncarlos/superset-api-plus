"""Sunburst (sunburst_v2, plugin-chart-echarts Sunburst, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import AdhocMetric, Metric, SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query, QueryFormColumn, custom_column
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, NumberFormatType, SunburstLabelType
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class SunburstOption(SingleMetricMixin, Option):
    """Sunburst params: one `metric` sizes the arcs and the `columns` hierarchy nests them (the dimension
    methods append to it); defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0)."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.SUNBURST_V2)
    columns: list[QueryFormColumn] = object_field(default_factory=list)
    # The plugin has no groupby control: the dimensions are `columns`.
    groupby: SerializableOptional[list[Any] | MissingField] = field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    # Optional: colors the arcs by its ratio to `metric` (categorical colors when absent).
    secondary_metric: SerializableOptional[Metric] = object_field(cls=AdhocMetric, default=None)
    color_scheme: str = default_string(default='supersetColors')
    linear_color_scheme: str = default_string(default='superset_seq_1')
    row_limit: SerializableOptional[int] = 10000
    show_labels: bool = False
    show_labels_threshold: float = 5
    show_total: bool = False
    label_type: SunburstLabelType = field(default_factory=lambda: SunburstLabelType.KEY)
    number_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    date_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    def validate(self) -> None:
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


@dataclass
class SunburstFormData(SunburstOption):
    pass


class SunburstQueryObject(Query):
    ...


@dataclass
class SunburstQueryContext(QueryContext):
    form_data: SunburstFormData = object_field(cls=SunburstFormData, default_factory=SunburstFormData)
    queries: list[SunburstQueryObject] = object_field(cls=Query, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return SunburstQueryObject


@dataclass
class SunburstChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.SUNBURST_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.SUNBURST_V2)
    params: SunburstOption = object_field(cls=SunburstOption, default_factory=SunburstOption)
    query_context: SunburstQueryContext = object_field(cls=SunburstQueryContext,
                                                       default_factory=SunburstQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return SunburstOption

"""Treemap (treemap_v2, plugin-chart-echarts Treemap, Superset 6.1.0)."""
from dataclasses import dataclass, field
from typing import ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import CurrencyFormat, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, NumberFormatType, TreemapLabelType
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class TreemapOption(SingleMetricMixin, Option):
    """Treemap params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    One `metric` sizes the rectangles and the `groupby` dimensions nest them (none: a single rectangle).
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.TREEMAP_V2)
    _require_groupby: ClassVar[bool] = False
    color_scheme: str = default_string(default='supersetColors')
    row_limit: SerializableOptional[int] = 10000
    show_labels: bool = True
    show_upper_labels: bool = True
    label_type: TreemapLabelType = field(default_factory=lambda: TreemapLabelType.KEY_VALUE)
    number_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)
    date_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)

    def validate(self) -> None:
        super().validate()
        if not self.metric and not self._read_from_superset:
            raise ValidationError(message='Field metric cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a metric.')


@dataclass
class TreemapFormData(TreemapOption):
    pass


class TreemapQueryObject(Query):
    ...


@dataclass
class TreemapQueryContext(QueryContext):
    form_data: TreemapFormData = object_field(cls=TreemapFormData, default_factory=TreemapFormData)
    queries: list[TreemapQueryObject] = object_field(cls=Query, default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return TreemapQueryObject


@dataclass
class TreemapChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.TREEMAP_V2
    viz_type: ChartType = field(default_factory=lambda: ChartType.TREEMAP_V2)
    params: TreemapOption = object_field(cls=TreemapOption, default_factory=TreemapOption)
    query_context: TreemapQueryContext = object_field(cls=TreemapQueryContext, default_factory=TreemapQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return TreemapOption

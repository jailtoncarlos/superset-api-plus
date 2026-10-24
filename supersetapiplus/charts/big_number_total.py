# supersetapiplus/charts/big_number_total.py

from dataclasses import dataclass, field
from typing import ClassVar

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, DateFormatType, NumberFormatType
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


@dataclass
class BigNumberTotalOption(SingleMetricMixin, Option):
    """Big Number params: one `metric` and no dimensions; defaults are the ones the UI gives a new chart."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER_TOTAL)
    # The plugin has no dimension control: groupby is absent.
    groupby: SerializableOptional[list] = field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    _sorts_by_metric: ClassVar[bool] = False

    header_font_size: float = 0.4
    subtitle_font_size: float = 0.15
    metric_name_font_size: float = 0.15
    show_metric_name: bool = False
    time_format: DateFormatType = field(default_factory=lambda: DateFormatType.SMART_DATE)
    y_axis_format: NumberFormatType = field(default_factory=lambda: NumberFormatType.SMART_NUMBER)
    force_timestamp_formatting: bool = False

    def _add_simple_groupby(self, column_name: str):
        raise ValidationError(message='A Big Number has no dimensions.',
                              solution='Filter the data with add_simple_filter, or use another chart type.')

    def _add_custom_groupby(self, label: str, column=None, sql_expression: str = None, aggregate=None):
        self._add_simple_groupby(label)


@dataclass
class BigNumberTotalFormData(BigNumberTotalOption):
    """Form data for Big Number Total; same fields as BigNumberTotalOption."""
    pass


@dataclass
class BigNumberTotalQueryObject(Query):
    """Query object for Big Number Total (no additional attributes)."""
    pass


@dataclass
class BigNumberTotalQueryContext(QueryContext):
    """
    Query context for Big Number Total:
      - queries: list of BigNumberTotalQueryObject
      - form_data: BigNumberTotalFormData
    """
    queries: list[BigNumberTotalQueryObject] = object_field(
        cls=BigNumberTotalQueryObject, default_factory=list
    )
    form_data: BigNumberTotalFormData = object_field(
        cls=BigNumberTotalFormData, default_factory=BigNumberTotalFormData
    )

    def _default_query_object_class(self) -> type[Query]:
        return BigNumberTotalQueryObject


@dataclass
class BigNumberTotalChart(Chart):
    """
    Chart class for Big Number Total. Encapsulates:
      - params: BigNumberTotalOption
      - query_context: BigNumberTotalQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.BIG_NUMBER_TOTAL
    viz_type: ChartType = field(default_factory=lambda: ChartType.BIG_NUMBER_TOTAL)
    params: BigNumberTotalOption = object_field(
        cls=BigNumberTotalOption, default_factory=BigNumberTotalOption
    )
    query_context: BigNumberTotalQueryContext = object_field(
        cls=BigNumberTotalQueryContext, default_factory=BigNumberTotalQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BigNumberTotalOption

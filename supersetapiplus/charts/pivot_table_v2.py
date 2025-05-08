"""Charts."""
from dataclasses import dataclass, field
from typing import List, Optional

from supersetapiplus.base.base import default_string, object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option, ChartVisualOptionsMixin
from supersetapiplus.charts.queries import AdhocMetric, CurrencyFormat, Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, LegendOrientationType, LegendType, DateFormatType, \
    NumberFormatType, TimeGrain, Orientation, ContributionType, SortSeriesType, StackStylyType, \
    TitlepositionType, LabelRotation, ComparisonType, FilterExpressionType
from supersetapiplus.exceptions import ChartValidationError
from supersetapiplus.typing import SerializableOptional


@dataclass
class PivotTableV2Option(Option):
    viz_type: ChartType = field(default_factory=lambda: ChartType.TIMESERIES_BAR)
    ...


@dataclass()
class PivotTableV2FormData(PivotTableV2Option):
    ...


@dataclass
class PivotTableV2QueryObject(Query):
    ...


@dataclass
class PivotTableV2QueryContext(QueryContext):
    queries: List[PivotTableV2QueryObject] = object_field(cls=PivotTableV2QueryObject, default_factory=list)
    form_data: PivotTableV2FormData = object_field(cls=PivotTableV2FormData, default_factory=PivotTableV2FormData)

    def _default_query_object_class(self) -> type[Query]:
        return PivotTableV2QueryObject


@dataclass
class PivotTableV2Chart(Chart):
    viz_type: ChartType = field(default_factory=lambda: ChartType.PIVOT_TALBE_V2)
    params: PivotTableV2Option = object_field(cls=PivotTableV2Option, default_factory=PivotTableV2Option)
    query_context: PivotTableV2QueryContext = object_field(cls=PivotTableV2QueryContext,
                                                           default_factory=PivotTableV2QueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return PivotTableV2Option
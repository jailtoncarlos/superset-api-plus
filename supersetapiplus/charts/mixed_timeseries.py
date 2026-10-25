
# supersetapiplus/charts/mixed_timeseries.py
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, ComparisonType, TimeGrain
from supersetapiplus.core.typing import SerializableOptional


class MixedTimeseriesOption(Option):
    """Mixed Time Series params: query A uses the plain keys, query B the `_b` keys (buildQuery of the plugin).

    Defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0) for the keys read by
    buildQuery; the other keys of the plugin are kept as read (lossless round trip).
    """
    # Dimensions are optional in the UI (a table in raw mode or with metrics only, mixed series, pivot rows).
    _require_groupby: ClassVar[bool] = False
    viz_type: ChartType = Field(default_factory=lambda: ChartType.MIXED_TIMESERIES)
    # X axis shared by both queries: a column name or an AdhocColumn; absent until set (the UI proposes the
    # dataset's time column, and the backend requires a datetime column when it is absent).
    x_axis: SerializableOptional[QueryFormColumn] = None
    row_limit: SerializableOptional[int] = 10000
    row_limit_b: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    order_desc_b: SerializableOptional[bool] = True
    truncate_metric: SerializableOptional[bool] = True
    truncate_metric_b: SerializableOptional[bool] = True
    comparison_type: SerializableOptional[ComparisonType] = Field(default_factory=lambda: ComparisonType.VALUES)
    comparison_type_b: SerializableOptional[ComparisonType] = Field(default_factory=lambda: ComparisonType.VALUES)
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)
    annotation_layers: SerializableOptional[list[Any]] = Field(default_factory=list)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.x_axis = column


class MixedTimeseriesFormData(MixedTimeseriesOption):
    """Form data for Mixed Time Series; same fields as MixedTimeseriesOption."""
    pass


class MixedTimeseriesQueryObject(Query):
    """Query object for Mixed Time Series (no additional attributes)."""
    pass


class MixedTimeseriesQueryContext(QueryContext):
    """
    Query context for Mixed Time Series:
      - queries: list of MixedTimeseriesQueryObject
      - form_data: MixedTimeseriesFormData
    """
    queries: list[MixedTimeseriesQueryObject] = Field(default_factory=list)
    form_data: MixedTimeseriesFormData = Field(default_factory=MixedTimeseriesFormData)

    def _default_query_object_class(self) -> type[Query]:
        return MixedTimeseriesQueryObject


class MixedTimeseriesChart(Chart):
    """
    Chart class for Mixed Time Series. Bundles:
      - params: MixedTimeseriesOption
      - query_context: MixedTimeseriesQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.MIXED_TIMESERIES
    # Superset may store query_context.form_data without the query B keys (metrics_b, groupby_b...).
    PARAMS_ONLY_FIELD_SUFFIXES = ('_b',)

    viz_type: ChartType = Field(default_factory=lambda: ChartType.MIXED_TIMESERIES)
    params: MixedTimeseriesOption = Field(default_factory=MixedTimeseriesOption)
    query_context: MixedTimeseriesQueryContext = Field(default_factory=MixedTimeseriesQueryContext)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        """X axis column shared by both queries (a column name or an AdhocColumn)."""
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return MixedTimeseriesOption

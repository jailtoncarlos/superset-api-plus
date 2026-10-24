# supersetapiplus/charts/mixed_timeseries.py

from dataclasses import dataclass, field

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, ComparisonType, TimeGrain
from supersetapiplus.typing import SerializableOptional


@dataclass
class MixedTimeseriesOption(Option):
    """Mixed Time Series params: query A uses the plain keys, query B the `_b` keys (buildQuery of the plugin).

    Defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0) for the keys read by
    buildQuery; the other keys of the plugin are kept as read (lossless round trip).
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.MIXED_TIMESERIES)
    # X axis shared by both queries: a column name or an AdhocColumn; absent until set (the UI proposes the
    # dataset's time column, and the backend requires a datetime column when it is absent).
    x_axis: SerializableOptional[QueryFormColumn] = object_field(default=None)
    row_limit: SerializableOptional[int] = 10000
    row_limit_b: SerializableOptional[int] = 10000
    order_desc: SerializableOptional[bool] = True
    order_desc_b: SerializableOptional[bool] = True
    truncate_metric: SerializableOptional[bool] = True
    truncate_metric_b: SerializableOptional[bool] = True
    comparison_type: SerializableOptional[ComparisonType] = field(default_factory=lambda: ComparisonType.VALUES)
    comparison_type_b: SerializableOptional[ComparisonType] = field(
        default_factory=lambda: ComparisonType.VALUES)
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)
    annotation_layers: SerializableOptional[list] = field(default_factory=list)

    def set_x_axis(self, column: QueryFormColumn) -> None:
        self.x_axis = column


@dataclass
class MixedTimeseriesFormData(MixedTimeseriesOption):
    """Form data for Mixed Time Series; same fields as MixedTimeseriesOption."""
    pass


@dataclass
class MixedTimeseriesQueryObject(Query):
    """Query object for Mixed Time Series (no additional attributes)."""
    pass


@dataclass
class MixedTimeseriesQueryContext(QueryContext):
    """
    Query context for Mixed Time Series:
      - queries: list of MixedTimeseriesQueryObject
      - form_data: MixedTimeseriesFormData
    """
    queries: list[MixedTimeseriesQueryObject] = object_field(
        cls=MixedTimeseriesQueryObject, default_factory=list
    )
    form_data: MixedTimeseriesFormData = object_field(
        cls=MixedTimeseriesFormData, default_factory=MixedTimeseriesFormData
    )

    def _default_query_object_class(self) -> type[Query]:
        return MixedTimeseriesQueryObject


@dataclass
class MixedTimeseriesChart(Chart):
    """
    Chart class for Mixed Time Series. Bundles:
      - params: MixedTimeseriesOption
      - query_context: MixedTimeseriesQueryContext
    """
    # Superset may store query_context.form_data without the query B keys (metrics_b, groupby_b...).
    PARAMS_ONLY_FIELD_SUFFIXES = ('_b',)

    viz_type: ChartType = field(default_factory=lambda: ChartType.MIXED_TIMESERIES)
    params: MixedTimeseriesOption = object_field(
        cls=MixedTimeseriesOption, default_factory=MixedTimeseriesOption
    )
    query_context: MixedTimeseriesQueryContext = object_field(
        cls=MixedTimeseriesQueryContext, default_factory=MixedTimeseriesQueryContext
    )

    def set_x_axis(self, column: QueryFormColumn) -> None:
        """X axis column shared by both queries (a column name or an AdhocColumn)."""
        self.params.set_x_axis(column)
        self.query_context.form_data.set_x_axis(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return MixedTimeseriesOption

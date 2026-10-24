# supersetapiplus/charts/box_plot.py

from dataclasses import dataclass, field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, TimeGrain, WhiskerOptions
from supersetapiplus.core.fields import object_field
from supersetapiplus.core.typing import SerializableNotToJson, SerializableOptional


@dataclass
class BoxPlotOption(Option):
    """Box Plot params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `groupby` holds the dimensions (one box per value) and `columns` the "Distribute across" columns, whose
    values are the points of each box (the UI proposes the dataset's time column).
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BOX_PLOT)
    # Dimensions are optional in the UI (one box when empty).
    _require_groupby: SerializableNotToJson[bool] = False
    columns: SerializableOptional[list[QueryFormColumn]] = object_field(default=None)
    whiskerOptions: SerializableOptional[WhiskerOptions] = field(default_factory=lambda: WhiskerOptions.TUKEY)
    row_limit: SerializableOptional[int] = 10000
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default_factory=lambda: TimeGrain.DAY)

    def _add_distribute_across(self, column: QueryFormColumn) -> None:
        if not isinstance(self.columns, list):
            self.columns = []
        self.columns.append(column)


@dataclass
class BoxPlotFormData(BoxPlotOption):
    """Form data for Box Plot; inherits same fields as BoxPlotOption."""
    pass


@dataclass
class BoxPlotQueryObject(Query):
    """Query object for Box Plot (no extra attributes required)."""
    pass


@dataclass
class BoxPlotQueryContext(QueryContext):
    """
    Query context for Box Plot, holding:
      - a list of BoxPlotQueryObject
      - the associated form_data
    """
    queries: list[BoxPlotQueryObject] = object_field(
        cls=BoxPlotQueryObject, default_factory=list
    )
    form_data: BoxPlotFormData = object_field(
        cls=BoxPlotFormData, default_factory=BoxPlotFormData
    )

    def _default_query_object_class(self) -> type[Query]:
        return BoxPlotQueryObject


@dataclass
class BoxPlotChart(Chart):
    """
    Chart class for Box Plot. Ties together:
      - params: BoxPlotOption
      - query_context: BoxPlotQueryContext
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.BOX_PLOT)
    params: BoxPlotOption = object_field(
        cls=BoxPlotOption, default_factory=BoxPlotOption
    )
    query_context: BoxPlotQueryContext = object_field(
        cls=BoxPlotQueryContext, default_factory=BoxPlotQueryContext
    )

    def add_distribute_across(self, column: QueryFormColumn) -> None:
        """Adds a "Distribute across" column: its values are the points summarized by each box."""
        self.params._add_distribute_across(column)
        self.query_context.form_data._add_distribute_across(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BoxPlotOption

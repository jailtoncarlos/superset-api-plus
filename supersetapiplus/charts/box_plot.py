# supersetapiplus/charts/box_plot.py
import re
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, TimeGrain, WhiskerOptions
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

# PERCENTILE_REGEX of plugin-chart-echarts/src/BoxPlot/buildQuery.ts (Superset 6.1.0).
PERCENTILE_WHISKERS = re.compile(r"(\d+)/(\d+) percentiles")


class BoxPlotOption(Option):
    """Box Plot params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    `groupby` holds the dimensions (one box per value) and `columns` the "Distribute across" columns, whose
    values are the points of each box (the UI proposes the dataset's time column).
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.BOX_PLOT)
    # Dimensions are optional in the UI (one box when empty).
    _require_groupby: ClassVar[bool] = False
    columns: SerializableOptional[list[QueryFormColumn]] = None
    # A preset, or custom "<low>/<high> percentiles" (freeForm control; see set_whisker_percentiles).
    whiskerOptions: SerializableOptional[WhiskerOptions | str] = Field(default_factory=lambda: WhiskerOptions.TUKEY)
    row_limit: SerializableOptional[int] = 10000
    time_grain_sqla: SerializableOptional[TimeGrain] = Field(default_factory=lambda: TimeGrain.DAY)

    def set_whisker_percentiles(self, low: int, high: int) -> None:
        """Whiskers at the `low` and `high` percentiles (the editor accepts any pair besides the presets)."""
        self.whiskerOptions = f"{low}/{high} percentiles"
        self._check_whiskers()

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        self._check_whiskers()

    def _check_whiskers(self) -> None:
        """A custom value follows PERCENTILE_REGEX of the BoxPlot buildQuery (Superset 6.1.0), with the
        percentiles the backend accepts (pandas_postprocessing/boxplot.py: low < high, both 0 to 100)."""
        value = self.whiskerOptions
        if not isinstance(value, str) or value in {option.value for option in WhiskerOptions}:
            return
        match = PERCENTILE_WHISKERS.search(value)
        if not match or not 0 <= int(match.group(1)) < int(match.group(2)) <= 100:
            raise ValidationError(message=f"Invalid whiskerOptions {value!r}.",
                                  solution='Use a WhiskerOptions preset or "<low>/<high> percentiles" with '
                                           '0 <= low < high <= 100.')

    def _add_distribute_across(self, column: QueryFormColumn) -> None:
        if not isinstance(self.columns, list):
            self.columns = []
        self.columns.append(column)


class BoxPlotFormData(BoxPlotOption):
    """Form data for Box Plot; inherits same fields as BoxPlotOption."""
    pass


class BoxPlotQueryObject(Query):
    """Query object for Box Plot (no extra attributes required)."""
    pass


class BoxPlotQueryContext(QueryContext):
    """
    Query context for Box Plot, holding:
      - a list of BoxPlotQueryObject
      - the associated form_data
    """
    queries: list[BoxPlotQueryObject] = Field(default_factory=list)
    form_data: BoxPlotFormData = Field(default_factory=BoxPlotFormData)

    def _default_query_object_class(self) -> type[Query]:
        return BoxPlotQueryObject


@dataclass
class BoxPlotChart(Chart):
    """
    Chart class for Box Plot. Ties together:
      - params: BoxPlotOption
      - query_context: BoxPlotQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.BOX_PLOT
    viz_type: ChartType = field(default_factory=lambda: ChartType.BOX_PLOT)
    params: BoxPlotOption = field(default_factory=BoxPlotOption)
    query_context: BoxPlotQueryContext = field(default_factory=BoxPlotQueryContext)

    def add_distribute_across(self, column: QueryFormColumn) -> None:
        """Adds a "Distribute across" column: its values are the points summarized by each box."""
        self.params._add_distribute_across(column)
        self.query_context.form_data._add_distribute_across(column)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return BoxPlotOption

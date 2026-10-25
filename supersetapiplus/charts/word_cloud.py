
# supersetapiplus/charts/word_cloud.py
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn, custom_column
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError


class WordCloudOption(SingleMetricMixin, Option):
    """Word Cloud params: one `metric` and one dimension in `series` (the words); UI defaults for a new chart."""
    viz_type: ChartType = Field(default_factory=lambda: ChartType.WORD_CLOUD)
    series: SerializableOptional[QueryFormColumn] = None
    # The plugin has no groupby control: the dimension is `series`.
    groupby: SerializableOptional[list[Any] | MissingField] = Field(default_factory=MissingField)
    _require_groupby: ClassVar[bool] = False
    row_limit: SerializableOptional[int] = 100
    size_from: int = 10
    size_to: int = 70

    def _set_series(self, column: QueryFormColumn) -> None:
        if self.series:
            raise ValidationError(message='A word cloud has a single dimension (series).',
                                  solution='Call add_simple_dimension or add_custom_dimension once.')
        self.series = column

    def _add_simple_groupby(self, column_name: str) -> None:
        self._set_series(column_name)

    def _add_custom_groupby(self, label: str, column: Any = None, sql_expression: str | None = None,
                            aggregate: Any = None) -> None:
        self._set_series(custom_column(label, column, sql_expression))


class WordCloudFormData(WordCloudOption):
    """Form data for Word Cloud; same fields as WordCloudOption."""
    pass


class WordCloudQueryObject(Query):
    """Query object for Word Cloud (no additional attributes)."""
    pass


class WordCloudQueryContext(QueryContext):
    """
    Query context for Word Cloud:
      - queries: list of WordCloudQueryObject
      - form_data: WordCloudFormData
    """
    queries: list[WordCloudQueryObject] = Field(default_factory=list)
    form_data: WordCloudFormData = Field(default_factory=WordCloudFormData)

    def _default_query_object_class(self) -> type[Query]:
        return WordCloudQueryObject


class WordCloudChart(Chart):
    """
    Chart class for Word Cloud. Consists of:
      - params: WordCloudOption
      - query_context: WordCloudQueryContext
    """
    VIZ_TYPE: ClassVar[ChartType] = ChartType.WORD_CLOUD
    viz_type: ChartType = Field(default_factory=lambda: ChartType.WORD_CLOUD)
    params: WordCloudOption = Field(default_factory=WordCloudOption)
    query_context: WordCloudQueryContext = Field(default_factory=WordCloudQueryContext)

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return WordCloudOption

# supersetapiplus/charts/word_cloud.py

from dataclasses import dataclass, field

from supersetapiplus.base.fields import object_field
from supersetapiplus.base.sentinels import MissingField
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import SingleMetricMixin
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn, custom_column
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional


@dataclass
class WordCloudOption(SingleMetricMixin, Option):
    """Word Cloud params: one `metric` and one dimension in `series` (the words); UI defaults for a new chart."""
    viz_type: ChartType = field(default_factory=lambda: ChartType.WORD_CLOUD)
    series: SerializableOptional[QueryFormColumn] = object_field(default=None)
    # The plugin has no groupby control: the dimension is `series`.
    groupby: SerializableOptional[list] = field(default_factory=MissingField)
    _require_groupby: SerializableNotToJson[bool] = False
    row_limit: SerializableOptional[int] = 100
    size_from: int = 10
    size_to: int = 70

    def _set_series(self, column: QueryFormColumn) -> None:
        if self.series:
            raise ValidationError(message='A word cloud has a single dimension (series).',
                                  solution='Call add_simple_dimension or add_custom_dimension once.')
        self.series = column

    def _add_simple_groupby(self, column_name: str):
        self._set_series(column_name)

    def _add_custom_groupby(self, label: str, column=None, sql_expression: str = None, aggregate=None):
        self._set_series(custom_column(label, column, sql_expression))


@dataclass
class WordCloudFormData(WordCloudOption):
    """Form data for Word Cloud; same fields as WordCloudOption."""
    pass


@dataclass
class WordCloudQueryObject(Query):
    """Query object for Word Cloud (no additional attributes)."""
    pass


@dataclass
class WordCloudQueryContext(QueryContext):
    """
    Query context for Word Cloud:
      - queries: list of WordCloudQueryObject
      - form_data: WordCloudFormData
    """
    queries: list[WordCloudQueryObject] = object_field(
        cls=WordCloudQueryObject, default_factory=list
    )
    form_data: WordCloudFormData = object_field(
        cls=WordCloudFormData, default_factory=WordCloudFormData
    )

    def _default_query_object_class(self) -> type[Query]:
        return WordCloudQueryObject


@dataclass
class WordCloudChart(Chart):
    """
    Chart class for Word Cloud. Consists of:
      - params: WordCloudOption
      - query_context: WordCloudQueryContext
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.WORD_CLOUD)
    params: WordCloudOption = object_field(
        cls=WordCloudOption, default_factory=WordCloudOption
    )
    query_context: WordCloudQueryContext = object_field(
        cls=WordCloudQueryContext, default_factory=WordCloudQueryContext
    )

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return WordCloudOption

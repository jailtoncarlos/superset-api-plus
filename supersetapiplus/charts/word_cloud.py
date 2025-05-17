# supersetapiplus/charts/word_cloud.py

from dataclasses import dataclass, field
from typing import List, Type

from supersetapiplus.base.fields import object_field
from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.options import Option, OptionListGroupByMixin
from supersetapiplus.charts.queries import Query
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType


@dataclass
class WordCloudOption(Option):
    """
    Configuration options for Word Cloud.

    Fields retained or added after diff:
      - datasource_id: numeric data source ID
      - datasource_type: data source type
      - groupby: list of grouping fields
    """
    viz_type: ChartType = field(default_factory=lambda: ChartType.WORD_CLOUD)


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
    queries: List[WordCloudQueryObject] = object_field(
        cls=WordCloudQueryObject, default_factory=list
    )
    form_data: WordCloudFormData = object_field(
        cls=WordCloudFormData, default_factory=WordCloudFormData
    )

    def _default_query_object_class(self) -> Type[Query]:
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
    def _default_option_class(cls) -> Type[Option]:
        return WordCloudOption

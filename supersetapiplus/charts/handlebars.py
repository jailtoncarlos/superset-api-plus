"""Handlebars chart (handlebars, plugin-chart-handlebars, Superset 6.1.0).

Renders the rows of a query as HTML through a Handlebars template (``handlebarsTemplate``, with the rows in
``data``) styled by an optional CSS (``styleTemplate``). The query is aggregate (dimensions and metrics) or raw
(``all_columns``), as in the table chart; buildQuery only normalizes the order (buildQuery.ts).
"""
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.charts import Chart
from supersetapiplus.charts.metric import Metric
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import Query, QueryFormColumn
from supersetapiplus.charts.query_context import QueryContext
from supersetapiplus.charts.types import ChartType, QueryModeType
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

#: The template Explore gives a new chart (controls/handlebarTemplate.tsx): one list item per row.
DEFAULT_TEMPLATE = '<ul class="data-list">\n  {{#each data}}\n    <li>{{stringify this}}</li>\n  {{/each}}\n</ul>'


class HandlebarsOption(Option):
    """Handlebars params; defaults are the ones the UI gives a new chart (tests/fixtures/ui_defaults_6.1.0).

    Aggregate mode: `groupby` (add_simple_dimension), `metrics` and `percent_metrics`, ordered by
    `timeseries_limit_metric`. Raw mode (add_raw_column): `all_columns`, ordered by `order_by_cols`.
    """
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HANDLEBARS)
    _require_groupby: ClassVar[bool] = False

    query_mode: QueryModeType = Field(default_factory=lambda: QueryModeType.AGGREGATE)
    all_columns: list[Any] = Field(default_factory=list)
    percent_metrics: list[Any] = Field(default_factory=list)
    order_by_cols: list[Any] = Field(default_factory=list)
    order_desc: bool = True
    row_limit: SerializableOptional[int] = 10000
    include_time: bool = False
    show_totals: bool = False
    timeseries_limit_metric: SerializableOptional[Metric] = None
    handlebarsTemplate: str = DEFAULT_TEMPLATE
    styleTemplate: SerializableOptional[str] = None

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset:  # what Superset stored is written back as read
            return
        if not self.handlebarsTemplate.strip():  # validateNonEmpty of the template control
            raise ValidationError(message="Field handlebarsTemplate cannot be empty.",
                                  solution="Set the template with set_template().")
        # validateAggControlValues (controls/shared.ts): in aggregate mode one of the three must have a value.
        if str(self.query_mode) == str(QueryModeType.AGGREGATE) \
                and not (self.metrics or self.groupby or self.percent_metrics):
            raise ValidationError(message="Group By, Metrics or Percentage Metrics must have a value.",
                                  solution="Use add_simple_metric, add_custom_metric or add_simple_dimension, or "
                                           "add_raw_column for a raw query.")


class HandlebarsFormData(HandlebarsOption):
    pass


class HandlebarsQueryObject(Query):
    pass


class HandlebarsQueryContext(QueryContext):
    form_data: HandlebarsFormData = Field(default_factory=HandlebarsFormData)
    queries: list[HandlebarsQueryObject] = Field(default_factory=list)

    def _default_query_object_class(self) -> type[Query]:
        return HandlebarsQueryObject


class HandlebarsChart(Chart):
    VIZ_TYPE: ClassVar[ChartType] = ChartType.HANDLEBARS
    viz_type: ChartType = Field(default_factory=lambda: ChartType.HANDLEBARS)
    params: HandlebarsOption = Field(default_factory=HandlebarsOption)
    query_context: HandlebarsQueryContext = Field(default_factory=HandlebarsQueryContext)

    def set_template(self, template: str, style: str | None = None) -> None:
        """The Handlebars template (the rows are ``data``; helpers of the plugin such as ``stringify``,
        ``dateFormat`` and ``formatNumber``) and, optionally, its CSS."""
        for target in self._option_targets():
            target.handlebarsTemplate = template
            if style is not None:
                target.styleTemplate = style

    def add_raw_column(self, column: QueryFormColumn) -> None:
        """Lists `column` (a column name or an AdhocColumn) and switches the query to raw mode (one row per record,
        no aggregation)."""
        for target in self._option_targets():
            target.query_mode = QueryModeType.RAW
            # absent from a chart read from Superset (MissingField): starts empty
            target.all_columns = [*(target.all_columns if isinstance(target.all_columns, list) else []), column]

    def _option_targets(self) -> list[HandlebarsOption]:
        form_data = getattr(self.query_context, "form_data", None)
        return [self.params] + ([form_data] if isinstance(form_data, HandlebarsOption) else [])

    @classmethod
    def _default_option_class(cls) -> type[Option]:
        return HandlebarsOption

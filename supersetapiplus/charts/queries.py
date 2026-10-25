import logging
import warnings
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.metric import AdhocMetricColumn, Metric, MetricHelper, MetricsListMixin, OrderByTyping
from supersetapiplus.charts.types import (
    ColumnType,
    CurrencyCodeType,
    CurrencyPositionType,
    FilterExpressionType,
    FilterOperatorType,
    HorizontalAlignType,
    MetricType,
    NumberFormatType,
    TimeGrain,
)
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import FilterValues, SerializableOptional
from supersetapiplus.deprecation import module_aliases
from supersetapiplus.exceptions import ValidationError

logger = logging.getLogger(__name__)

class CurrencyFormat(ApiModel):
    symbolPosition: SerializableOptional[CurrencyPositionType] = None
    symbol: SerializableOptional[CurrencyCodeType] = None


class ColumnConfig(ApiModel):
    d3NumberFormat: SerializableOptional[NumberFormatType] = Field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)
    d3SmallNumberFormat: SerializableOptional[NumberFormatType] = None
    horizontalAlign: SerializableOptional[HorizontalAlignType] = None

    alignPositiveNegative: SerializableOptional[bool] = None
    colorPositiveNegative: SerializableOptional[bool] = None
    showCellBars: SerializableOptional[bool] = None
    columnWidth: SerializableOptional[int] = None
    currency_format: SerializableOptional[CurrencyFormat] = None


class QueryExtra(ApiModel):
    time_grain_sqla: SerializableOptional[TimeGrain] = None
    having: str = ''
    where: str = ''


class AdhocColumn(ApiModel):
    """Custom SQL column (superset-ui-core AdhocColumn): a dimension defined by an expression."""
    hasCustomLabel: SerializableOptional[bool] = None
    label: str = ''
    sqlExpression: str = ''
    expressionType: FilterExpressionType = Field(default_factory=lambda: FilterExpressionType.CUSTOM_SQL)
    timeGrain: SerializableOptional[TimeGrain] = None
    columnType: SerializableOptional[ColumnType] = None


QueryFormColumn = AdhocColumn | str


def custom_column(label: str, column: AdhocMetricColumn | None = None, sql_expression: str | None = None,
                  aggregate: MetricType | None = None) -> AdhocColumn:
    """Custom dimension as the UI stores it: an AdhocColumn with a SQL expression (a column has no aggregate)."""
    if aggregate is not None:
        warnings.warn("A dimension has no aggregate: the aggregate argument is ignored (use a metric instead).",
                      DeprecationWarning, stacklevel=3)
    expression = sql_expression or (column.column_name if column else None) or label
    return AdhocColumn(label=label, sqlExpression=expression, hasCustomLabel=True)


class QueryFilterClause(ApiModel):
    col: QueryFormColumn
    val: SerializableOptional[FilterValues]
    op: FilterOperatorType = Field(default_factory=lambda: FilterOperatorType.EQUALS)


class ColumnsMixin(ApiModel):
    columns: SerializableOptional[list[AdhocColumn | Metric]] = Field(default_factory=list)

    def _editable_columns(self) -> list[AdhocColumn | Metric]:
        if not isinstance(self.columns, list):
            self.columns = []
        return self.columns

    def _add_simple_columns(self, column_name:str) -> None:
        self._editable_columns().append(column_name)

    def _add_custom_columns(self, label: str,
                            column: AdhocMetricColumn | None = None,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None) -> None:
        self._editable_columns().append(custom_column(label, column, sql_expression, aggregate))


class OrderByMixin(ApiModel):
    orderby: SerializableOptional[list[OrderByTyping] | MissingField] = Field(default_factory=list)

    def _editable_orderby(self) -> list[OrderByTyping]:
        if not isinstance(self.orderby, list):
            self.orderby = []
        return self.orderby

    def _add_simple_orderby(self, column_name: str,
                            sort_ascending: bool) -> None:
        self._editable_orderby().append((column_name, sort_ascending))

    def _add_custom_orderby(self, label: str,
                            sort_ascending: bool,
                            column: AdhocMetricColumn | None,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None) -> None:
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self._editable_orderby().append((metric, sort_ascending))

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if getattr(self, "_read_from_superset", False):  # e.g. tables saved without ordering
            return
        if not isinstance(self.orderby, MissingField) and not self.orderby:
            raise ValidationError(message='Field orderby cannot be empty.',
                                  solution='Set the "automatic_order=OrderBy(automate=True)" argument in the '
                                           'add_simple_metric or add_custom_metric methods. If you want to customize '
                                           'a different order, use the add_simple_orderby or add_custom_orderby methods.')


class Query(MetricsListMixin, ColumnsMixin, OrderByMixin, ApiModel):
    row_limit: SerializableOptional[int] = 100
    series_limit: SerializableOptional[int] = 0
    series_limit_metric: SerializableOptional[Metric] = None

    filters: list[QueryFilterClause] = Field(default_factory=list)
    extras: QueryExtra = Field(default_factory=QueryExtra)

    applied_time_extras: dict[str, Any] = Field(default_factory=dict)
    url_params: dict[str, Any] = Field(default_factory=dict)
    custom_params: dict[str, Any] = Field(default_factory=dict)
    custom_form_data: dict[str, Any] = Field(default_factory=dict)
    annotation_layers: list[Any] = Field(default_factory=list)

    # Additional fields, as needed in the API JSON
    row_offset: SerializableOptional[int] = None
    order_desc: SerializableOptional[bool] = None

    # Whether a query built in code needs metrics (False for plugins without a metric, e.g. histogram_v2).
    _requires_metrics: ClassVar[bool] = True

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._requires_metrics and not self.metrics and not getattr(self, "_read_from_superset", False):
            raise ValidationError(message='Field metrics cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')

    def _add_simple_filter(self, column_name: QueryFormColumn,
                           value: FilterValues | None,
                           operator: FilterOperatorType = FilterOperatorType.EQUALS) -> None:
        query_filter_clause = QueryFilterClause(col=column_name, val=value, op=operator)
        self.filters.append(query_filter_clause)

    def _add_extra_where(self, sql: str) -> None:
        if self.extras.where:
            self.extras.where = f'{self.extras.where} AND '
        self.extras.where = self.extras.where + f'({sql})'

    def _add_extra_having(self, sql: str) -> None:
        raise NotImplementedError


# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"QuerieExtra": "QueryExtra"})

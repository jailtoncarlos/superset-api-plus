import logging
import warnings
from dataclasses import dataclass, field

from supersetapiplus.charts.metric import AdhocMetric, AdhocMetricColumn, Metric, MetricHelper, MetricsListMixin, OrderByTyping
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
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import FilterValues, SerializableOptional
from supersetapiplus.deprecation import module_aliases
from supersetapiplus.exceptions import ValidationError

logger = logging.getLogger(__name__)

@dataclass
class CurrencyFormat(SerializableModel):
    symbolPosition: SerializableOptional[CurrencyPositionType] = field(default=None)
    symbol: SerializableOptional[CurrencyCodeType] = field(default=None)


@dataclass
class ColumnConfig(SerializableModel):
    d3NumberFormat: SerializableOptional[NumberFormatType] = field(default_factory=lambda: NumberFormatType.ORIGINAL_VALUE)
    d3SmallNumberFormat: SerializableOptional[NumberFormatType] = field(default=None)
    horizontalAlign: SerializableOptional[HorizontalAlignType] = field(default=None)

    alignPositiveNegative: SerializableOptional[bool] = None
    colorPositiveNegative: SerializableOptional[bool] = None
    showCellBars: SerializableOptional[bool] = None
    columnWidth: SerializableOptional[int] = None
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)


@dataclass
class QueryExtra(SerializableModel):
    time_grain_sqla: SerializableOptional[TimeGrain] = None
    having: str = ''
    where: str = ''


@dataclass
class AdhocColumn(SerializableModel):
    """Custom SQL column (superset-ui-core AdhocColumn): a dimension defined by an expression."""
    hasCustomLabel: SerializableOptional[bool] = field(default=None)
    label: str = default_string()
    sqlExpression: str = default_string()
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.CUSTOM_SQL)
    timeGrain: SerializableOptional[TimeGrain] = field(default=None)
    columnType: SerializableOptional[ColumnType] = field(default=None)


QueryFormColumn = AdhocColumn | str


def custom_column(label: str, column: AdhocMetricColumn | None = None, sql_expression: str | None = None,
                  aggregate: MetricType | None = None) -> AdhocColumn:
    """Custom dimension as the UI stores it: an AdhocColumn with a SQL expression (a column has no aggregate)."""
    if aggregate is not None:
        warnings.warn("A dimension has no aggregate: the aggregate argument is ignored (use a metric instead).",
                      DeprecationWarning, stacklevel=3)
    expression = sql_expression or (column.column_name if column else None) or label
    return AdhocColumn(label=label, sqlExpression=expression, hasCustomLabel=True)


@dataclass
class QueryFilterClause(SerializableModel):
    col: QueryFormColumn
    val: SerializableOptional[FilterValues]
    op: FilterOperatorType = field(default_factory=lambda: FilterOperatorType.EQUALS)


@dataclass
class ColumnsMixin:
    columns: SerializableOptional[list[Metric]] = object_field(cls=AdhocMetric, default_factory=list)

    def _add_simple_columns(self, column_name:str) -> None:
        self.columns.append(column_name)

    def _add_custom_columns(self, label: str,
                            column: AdhocMetricColumn | None = None,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None) -> None:
        self.columns.append(custom_column(label, column, sql_expression, aggregate))


@dataclass
class OrderByMixin:
    orderby: SerializableOptional[list[OrderByTyping]] = object_field(default_factory=list)

    def _add_simple_orderby(self, column_name: str,
                            sort_ascending: bool) -> None:
        self.orderby.append((column_name, sort_ascending))

    def _add_custom_orderby(self, label: str,
                            sort_ascending: bool,
                            column: AdhocMetricColumn,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None) -> None:
        metric = MetricHelper.get_metric(label, column, sql_expression, aggregate)
        self.orderby.append((metric, sort_ascending))

    def validate(self) -> None:
        super().validate()
        if getattr(self, "_read_from_superset", False):  # e.g. tables saved without ordering
            return
        if not isinstance(self.orderby, MissingField) and not self.orderby:
            raise ValidationError(message='Field orderby cannot be empty.',
                                  solution='Set the "automatic_order=OrderBy(automate=True)" argument in the '
                                           'add_simple_metric or add_custom_metric methods. If you want to customize '
                                           'a different order, use the add_simple_orderby or add_custom_orderby methods.')


@dataclass
class Query(MetricsListMixin, ColumnsMixin, OrderByMixin, SerializableModel):
    row_limit: SerializableOptional[int] = 100
    series_limit: SerializableOptional[int] = 0
    series_limit_metric: SerializableOptional[Metric] = object_field(default=None)

    filters: list[QueryFilterClause] = object_field(cls=QueryFilterClause, default_factory=list)
    extras: QueryExtra = object_field(cls=QueryExtra, default_factory=QueryExtra)

    applied_time_extras: dict = field(default_factory=dict)
    url_params: dict = field(default_factory=dict)
    custom_params: dict = field(default_factory=dict)
    custom_form_data: dict = field(default_factory=dict)
    annotation_layers: list = field(default_factory=list)

    # Additional fields, as needed in the API JSON
    row_offset: SerializableOptional[int] = None
    order_desc: SerializableOptional[bool] = None

    def __post_init__(self) -> None:
        super().__post_init__()

    def validate(self) -> None:
        super().validate()
        if not self.metrics and not getattr(self, "_read_from_superset", False):
            raise ValidationError(message='Field metrics cannot be empty.',
                                  solution='Use one of the add_simple_metric or add_custom_metric methods to add a queries.')

    def _add_simple_filter(self, column_name: QueryFormColumn,
                           value: FilterValues,
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

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar

from supersetapiplus.charts.filters import AdhocFilterClause
from supersetapiplus.charts.metric import (
    AdhocMetric,
    AdhocMetricColumn,
    MetricsListMixin,
)
from supersetapiplus.charts.queries import CurrencyFormat, custom_column
from supersetapiplus.charts.types import (
    ChartType,
    ComparisonType,
    FilterClausesType,
    FilterExpressionType,
    FilterOperatorType,
    LegendOrientationType,
    LegendType,
    MetricType,
    ResultFormat,
    ResultType,
    TimeGrain,
)
from supersetapiplus.core.fields import default_string, object_field
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ChartVisualOptionsMixin:
    color_scheme: str = default_string(default='supersetColors')
    show_legend: SerializableOptional[bool] = True
    legendType: LegendType = field(default_factory=lambda: LegendType.SCROLL)
    legendOrientation: LegendOrientationType = field(default_factory=lambda: LegendOrientationType.TOP)
    legendMargin: SerializableOptional[int] = None  # TextControl with isInt: a number or null
    currency_format: SerializableOptional[CurrencyFormat] = object_field(cls=CurrencyFormat, default=None)


@dataclass
class OptionListGroupByMixin:
    # Dimensions: column names or AdhocColumn dicts; MissingField when the key was absent in the JSON read.
    groupby: list[Any] | MissingField | None = object_field(cls=AdhocMetric, default_factory=list)

    # by default, every chart requires groupby
    _require_groupby: ClassVar[bool] = True

    def validate(self) -> None:
        super().validate()  # type: ignore[misc]  # mixin: the next class in the MRO validates too
        # Only for charts built in code whose plugin requires a dimension (see _read_from_superset).
        if self._require_groupby and not getattr(self, "_read_from_superset", False) \
                and not isinstance(self.groupby, MissingField) \
                and not self.groupby:
            raise ValidationError(
                message='Field groupby cannot be empty.',
                solution='Use one of the add_simple_groupby or add_custom_groupby methods to add a groupby.'
            )

    def _editable_groupby(self) -> list[Any]:
        if not isinstance(self.groupby, list):
            self.groupby = []
        return self.groupby

    def _add_simple_groupby(self, column_name: str) -> None:
        self._editable_groupby().append(column_name)

    def _add_custom_groupby(self, label: str,
                            column: AdhocMetricColumn | None = None,
                            sql_expression: str | None = None,
                            aggregate: MetricType | None = None) -> None:
        self._editable_groupby().append(custom_column(label, column, sql_expression, aggregate))


@dataclass
class Option(MetricsListMixin, OptionListGroupByMixin, SerializableModel):
    viz_type: ChartType | None = field(default=None)
    slice_id: SerializableOptional[int] = field(default=None)

    datasource: str | None = field(default=None)

    extra_form_data: dict[str, Any] = field(default_factory=dict)
    # Absent unless the plugin has a row limit control (each chart class sets the UI default).
    row_limit: SerializableOptional[int] = None

    adhoc_filters: list[AdhocFilterClause] = object_field(cls=AdhocFilterClause, default_factory=list)
    dashboards: list[int] = field(default_factory=list)

    force: SerializableOptional[bool] = field(default=None)
    result_format: SerializableOptional[ResultFormat] = field(default=None)
    result_type: SerializableOptional[ResultType] = field(default=None)

    cache_timeout: SerializableOptional[int] = field(default=None)
    time_grain_sqla: SerializableOptional[TimeGrain] = field(default=None)
    order_desc: SerializableOptional[bool] = field(default=None)

    comparison_type: SerializableOptional[ComparisonType] = field(default=None)

    def validate(self) -> None:
        super().validate()

    def __post_init__(self) -> None:
        super().__post_init__()
        # None becomes an empty list; MissingField (key absent from the JSON read) is kept so that
        # re-reading does not add "groupby": [] to charts that did not have it.
        if self.groupby is None:
            self.groupby = []

    def add_dashboard(self, dashboard_id: int) -> None:
        dashboards = set(self.dashboards)
        dashboards.add(dashboard_id)
        self.dashboards = list(dashboards)

    def _adhoc_filters(self,
                       expression_type: FilterExpressionType,
                       clause: FilterClausesType,
                       subject: str | None = None,
                       comparator: str | None = None,
                       sql_expression: str | None = None,
                       operator: FilterOperatorType | None = None) -> None:
        operator_id = None
        if operator:
            operator_id = operator.name

        adhoc_filter_clause = AdhocFilterClause(expressionType=expression_type,
                                                subject=subject,
                                                operator=operator,
                                                operatorId=operator_id,
                                                comparator=comparator,
                                                clause=clause,
                                                sqlExpression=sql_expression)
        if not isinstance(self.adhoc_filters, list):  # absent from a chart read from Superset
            self.adhoc_filters = []
        self.adhoc_filters.append(adhoc_filter_clause)

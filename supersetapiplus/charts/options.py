import logging
import re
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.charts.filters import AdhocFilterClause
from supersetapiplus.charts.metric import (
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
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import FilterValues, SerializableOptional
from supersetapiplus.exceptions import ValidationError

logger = logging.getLogger(__name__)


# Time format controls of the chart plugins (free-form, DateFormatType holds the suggestions).
TIME_FORMAT_FIELDS = ("date_format", "time_format", "x_axis_time_format", "table_timestamp_format",
                      "tooltipTimeFormat")
# Tokens of moment.js date formats ("DD/MM/YYYY"): Superset 6 formats dates with d3-time-format
# (superset-ui-core/src/time-format, "%d/%m/%Y"), which prints them as literal text.
_MOMENT_TOKENS = re.compile(r"YYYY|YY|DD|Do|HH|hh|mm|ss|MMM|MM")


def unbounded() -> list[float | None]:
    """Default of the axis and value bounds controls: no minimum and no maximum ([null, null])."""
    return [None, None]


def check_time_formats(option: object) -> None:
    """Time formats are "smart_date" or d3-time-format patterns, not moment.js ones."""
    for name in TIME_FORMAT_FIELDS:
        value = getattr(option, name, None)
        if isinstance(value, str) and "%" not in value and _MOMENT_TOKENS.search(value):
            raise ValidationError(message=f"{name} {value!r} is a moment.js format; Superset would show it as text.",
                                  solution='Use a d3-time-format pattern (e.g. "%d/%m/%Y") or DateFormatType.')


class ChartVisualOptionsMixin(ApiModel):
    color_scheme: str = 'supersetColors'
    show_legend: SerializableOptional[bool] = True
    legendType: LegendType = Field(default_factory=lambda: LegendType.SCROLL)
    legendOrientation: LegendOrientationType = Field(default_factory=lambda: LegendOrientationType.TOP)
    legendMargin: SerializableOptional[int] = None  # TextControl with isInt: a number or null
    currency_format: SerializableOptional[CurrencyFormat] = None


class OptionListGroupByMixin(ApiModel):
    # Dimensions: column names or AdhocColumn dicts; MissingField when the key was absent in the JSON read.
    groupby: list[Any] | MissingField | None = Field(default_factory=list)

    # by default, every chart requires groupby
    _require_groupby: ClassVar[bool] = True

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
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


class Option(MetricsListMixin, OptionListGroupByMixin, ApiModel):
    viz_type: ChartType | None = None
    slice_id: SerializableOptional[int] = None

    datasource: str | None = None

    extra_form_data: dict[str, Any] = Field(default_factory=dict)
    # Absent unless the plugin has a row limit control (each chart class sets the UI default).
    row_limit: SerializableOptional[int] = None

    adhoc_filters: list[AdhocFilterClause] = Field(default_factory=list)
    dashboards: list[int] = Field(default_factory=list)

    force: SerializableOptional[bool] = None
    result_format: SerializableOptional[ResultFormat] = None
    result_type: SerializableOptional[ResultType] = None

    cache_timeout: SerializableOptional[int] = None
    time_grain_sqla: SerializableOptional[TimeGrain] = None
    order_desc: SerializableOptional[bool] = None

    comparison_type: SerializableOptional[ComparisonType] = None

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if not self._read_from_superset:  # what Superset stored is written back as read
            check_time_formats(self)

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
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
                       comparator: FilterValues | None = None,
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

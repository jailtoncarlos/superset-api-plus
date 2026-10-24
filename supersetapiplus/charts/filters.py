from dataclasses import dataclass, field

from supersetapiplus.charts.types import FilterClausesType, FilterExpressionType, FilterOperatorType
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.typing import FilterValues, SerializableOptional
from supersetapiplus.exceptions import ValidationError

# Operators of the adhoc filter control (src/explore/constants.ts, Superset 6.1.0; checked in
# test_enum_conformance.py): MULTI_OPERATORS take a list of values, DISABLE_INPUT_OPERATORS take no value.
MULTI_OPERATORS = frozenset({FilterOperatorType.IN, FilterOperatorType.NOT_IN})
DISABLE_INPUT_OPERATORS = frozenset({FilterOperatorType.IS_NOT_NULL, FilterOperatorType.IS_NULL,
                                     FilterOperatorType.LATEST_PARTITION, FilterOperatorType.IS_TRUE,
                                     FilterOperatorType.IS_FALSE})


def filter_comparator(operator: FilterOperatorType, value: FilterValues | None) -> FilterValues | None:
    """The comparator of a simple adhoc filter, as the filter control stores it.

    IN and NOT IN take a list (a single value becomes a one-item list); the IS ... operators take no value;
    the others take one value: Superset would keep only the first item of a list (``filter_values_handler``
    in superset/models/helpers.py), so a list is rejected. A missing value is rejected where one is needed.
    """
    if operator in DISABLE_INPUT_OPERATORS:
        if value is not None:
            raise ValidationError(f"Operator {operator} takes no value, got {value!r}.",
                                  solution="Call add_simple_filter without a value.")
        return None
    if value is None:
        raise ValidationError(f"Operator {operator} needs a value.", solution="Pass the value to filter by.")
    if operator in MULTI_OPERATORS:
        return list(value) if isinstance(value, (list, tuple)) else [value]
    if isinstance(value, (list, tuple)):
        raise ValidationError(f"Operator {operator} takes a single value, got a list {list(value)!r}.",
                              solution="Use FilterOperatorType.IN for a list of values.")
    return value

#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset/utils/core.py#L137


@dataclass
class AdhocFilterClause(SerializableModel):
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.SIMPLE)
    subject: str | None = field(default=None)
    operator: FilterOperatorType | None = field(default=None)
    comparator: FilterValues | None = field(default=None)
    clause: FilterClausesType = field(default_factory=lambda: FilterClausesType.WHERE)
    sqlExpression: str | None = field(default=None)
    operatorId: SerializableOptional[str] = field(default=None)

    isExtra: SerializableOptional[bool] = field(default=None)
    isNew: SerializableOptional[bool] = field(default=None)

    datasourceWarning: SerializableOptional[bool] = field(default=None)
    filterOptionName: SerializableOptional[str] = field(default=None)


from pydantic import Field

from supersetapiplus.charts.types import FilterClausesType, FilterExpressionType, FilterOperatorType
from supersetapiplus.core.api_model import ApiModel
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


class AdhocFilterClause(ApiModel):
    expressionType: FilterExpressionType = Field(default_factory=lambda: FilterExpressionType.SIMPLE)
    subject: str | None = None
    operator: FilterOperatorType | None = None
    comparator: FilterValues | None = None
    clause: FilterClausesType = Field(default_factory=lambda: FilterClausesType.WHERE)
    sqlExpression: str | None = None
    operatorId: SerializableOptional[str] = None

    isExtra: SerializableOptional[bool] = None
    isNew: SerializableOptional[bool] = None

    datasourceWarning: SerializableOptional[bool] = None
    filterOptionName: SerializableOptional[str] = None

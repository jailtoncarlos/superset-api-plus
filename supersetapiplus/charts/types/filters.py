"""Adhoc filter operators, expression types and clauses."""

from supersetapiplus.core.enums import StringEnum, deprecate_members


class FilterOperatorType(StringEnum):
    """Adhoc filter operators (superset/utils/core.py FilterOperator, Superset 6.1.0).

    The member name becomes the filter's `operatorId` and follows the frontend `Operators` enum
    (src/explore/constants.ts); the old names are kept as aliases.
    """
    EQUALS = '=='
    NOT_EQUALS = '!='
    LESS_THAN = '<'
    LESS_THAN_OR_EQUAL = '<='
    GREATER_THAN = '>'
    GREATER_THAN_OR_EQUAL = '>='
    IN = 'IN'
    NOT_IN = 'NOT IN'
    LIKE = 'LIKE'
    NOT_LIKE = 'NOT LIKE'
    ILIKE = 'ILIKE'
    NOT_ILIKE = 'NOT ILIKE'
    IS_NOT_NULL = 'IS NOT NULL'
    IS_NULL = 'IS NULL'
    LATEST_PARTITION = 'LATEST PARTITION'
    IS_TRUE = 'IS TRUE'
    IS_FALSE = 'IS FALSE'
    TEMPORAL_RANGE = 'TEMPORAL_RANGE'

class FilterExpressionType(StringEnum):
    SIMPLE = 'SIMPLE'
    CUSTOM_SQL = 'SQL'

class FilterClausesType(StringEnum):
    HAVING = 'HAVING'
    WHERE = 'WHERE'


# Old names, kept as aliases that emit DeprecationWarning.
deprecate_members(FilterOperatorType, {"NOT_EQUAL": "NOT_EQUALS"})

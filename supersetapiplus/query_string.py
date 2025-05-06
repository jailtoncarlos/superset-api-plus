from enum import Enum
from typing import Any, Dict, List


class QueryOperator(str, Enum):
    """
    Enumeration of supported query operators used in Superset API filters.
    """
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not in"
    LIKE = "like"
    ILIKE = "ilike"
    IS_NULL = "is null"
    IS_NOT_NULL = "is not null"
    TEMPORAL_RANGE = "TEMPORAL_RANGE"  # For date/time filters


class QueryStringFilter:
    """
    Utility class to build query string filters for Superset API requests.

    This class helps build structured filters to be passed to endpoints that
    accept query parameters such as `/api/v1/chart/`, `/api/v1/dashboard/`, etc.

    Attributes:
        _filters (List[Dict[str, Any]]): Internal list storing all filters.

    Methods:
        add(column: str, operator: QueryOperator, value: Any) -> None:
            Adds a new filter entry.
        filters() -> List[Dict[str, Any]]:
            Returns the list of filters as a list of dictionaries.
    """

    def __init__(self):
        self._filters: List[Dict[str, Any]] = []

    def add(self, column: str, operator: QueryOperator, value: Any) -> None:
        """
        Add a new filter to the filter list.

        Args:
            column (str): The column name to be filtered.
            operator (QueryOperator): The comparison operator.
            value (Any): The value to be used in the comparison.
        """
        self._filters.append({
            "col": column,
            "opr": operator.value,
            "value": value
        })

    @property
    def filters(self) -> List[Dict[str, Any]]:
        """
        Returns:
            List[Dict[str, Any]]: The list of filters in dictionary format.
        """
        return self._filters

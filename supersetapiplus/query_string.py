from enum import Enum
from typing import Any


class QueryOperator(str, Enum):
    """
    Operadores de filtro das listagens da API REST (Flask-AppBuilder), enviados em `q.filters[].opr`.

    Conferidos contra o /_info?q=(keys:!(filters)) do Superset 6.1.0. Cada coluna aceita só parte
    deles; recursos têm ainda filtros próprios (ex.: chart_all_text, dashboard_is_favorite), que
    podem ser passados como string em QueryStringFilter.add.
    """
    EQUAL = "eq"
    NOT_EQUAL = "neq"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    CONTAINS = "ct"
    NOT_CONTAINS = "nct"
    STARTS_WITH = "sw"
    NOT_STARTS_WITH = "nsw"
    ENDS_WITH = "ew"
    NOT_ENDS_WITH = "new"
    IN = "in"
    NOT_IN = "not_in"
    RELATION_ONE_TO_MANY = "rel_o_m"
    NOT_RELATION_ONE_TO_MANY = "nrel_o_m"
    RELATION_MANY_TO_MANY = "rel_m_m"


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
        self._filters: list[dict[str, Any]] = []

    def add(self, column: str, operator: QueryOperator | str, value: Any) -> None:
        """
        Add a new filter to the filter list.

        Args:
            column (str): The column name to be filtered.
            operator (QueryOperator | str): The comparison operator, or the name of a resource-specific
                filter (e.g. "chart_all_text").
            value (Any): The value to be used in the comparison.
        """
        self._filters.append({
            "col": column,
            "opr": operator.value if isinstance(operator, QueryOperator) else str(operator),
            "value": value
        })

    @property
    def filters(self) -> list[dict[str, Any]]:
        """
        Returns:
            List[Dict[str, Any]]: The list of filters in dictionary format.
        """
        return self._filters

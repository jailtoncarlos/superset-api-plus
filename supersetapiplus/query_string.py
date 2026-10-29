from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any


class QueryOperator(str, Enum):
    """
    Filter operators of the REST API listings (Flask-AppBuilder), sent in `q.filters[].opr`.

    Checked against /_info?q=(keys:!(filters)) of Superset 6.1.0. Each column accepts only some
    of them; resources also have their own filters (e.g. chart_all_text, dashboard_is_favorite), which
    can be passed as a string to QueryStringFilter.add.

    The text operators are case-insensitive ``ILIKE`` patterns without an ``ESCAPE`` clause (Flask-AppBuilder 5,
    models/sqla/filters.py): a ``_`` or ``%`` in the value is a wildcard. ``find``, ``find_all`` and ``count`` check
    the results of STARTS_WITH, ENDS_WITH and CONTAINS again, so they match the value literally; the negated
    operators (NOT_STARTS_WITH...) leave out the names a wildcard matches, which cannot be recovered.
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


# Operators whose value Flask-AppBuilder puts in an ILIKE pattern, with the literal check of a result (lowercase text,
# lowercase value). Escaping the value is not portable: the default LIKE escape character is a backslash on
# PostgreSQL and MySQL and there is none on SQLite, and FAB adds no ESCAPE clause.
_LIKE_CHECKS: dict[str, Callable[[str, str], bool]] = {
    QueryOperator.STARTS_WITH.value: str.startswith,
    QueryOperator.ENDS_WITH.value: str.endswith,
    QueryOperator.CONTAINS.value: lambda text, value: value in text,
}


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

    def __init__(self) -> None:
        self._filters: list[dict[str, Any]] = []

    def add(self, column: str, operator: QueryOperator | str, value: object) -> None:
        """
        Add a new filter to the filter list.

        Args:
            column (str): The column name to be filtered.
            operator (QueryOperator | str): The comparison operator, or the name of a resource-specific
                filter (e.g. "chart_all_text").
            value: The value to be used in the comparison (serialized by rison: a value or a list of values).
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

    @property
    def wildcard_columns(self) -> list[str]:
        """Columns of the text filters whose value holds a LIKE wildcard (``_`` or ``%``): the server results must be
        checked again (see :meth:`matches`)."""
        return [f["col"] for f in self._wildcard_filters()]

    def matches(self, item: Mapping[str, Any]) -> bool:
        """Whether a listed item matches the text filters with wildcards literally (case-insensitive, as ILIKE)."""
        return all(isinstance(item.get(f["col"]), str)
                   and _LIKE_CHECKS[f["opr"]](item[f["col"]].lower(), f["value"].lower())
                   for f in self._wildcard_filters())

    def _wildcard_filters(self) -> list[dict[str, Any]]:
        return [f for f in self._filters if f["opr"] in _LIKE_CHECKS and isinstance(f["value"], str)
                and ("_" in f["value"] or "%" in f["value"]) and "." not in f["col"]]

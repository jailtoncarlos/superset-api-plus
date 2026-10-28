"""Text filters of the REST listings checked literally (supersetapiplus/query_string.py).

Flask-AppBuilder 5 turns STARTS_WITH, ENDS_WITH and CONTAINS into ILIKE patterns without an ESCAPE clause
(models/sqla/filters.py), so a "_" or "%" in the value is a wildcard on the server; the integration test
(tests/integration/test_charts.py) shows it on Superset. Here, the check of the listed items, without HTTP.
"""
import pytest

from supersetapiplus.query_string import QueryOperator, QueryStringFilter


def text_filter(operator: QueryOperator, value: str) -> QueryStringFilter:
    query_filter = QueryStringFilter()
    query_filter.add("slice_name", operator, value)
    return query_filter


@pytest.mark.parametrize("operator, value, name, matches", [
    (QueryOperator.STARTS_WITH, "zz_test_", "zz_test_chart", True),
    (QueryOperator.STARTS_WITH, "zz_test_", "zzXtestYchart", False),  # what ILIKE 'zz_test_%' also returns
    (QueryOperator.STARTS_WITH, "ZZ_Test_", "zz_test_chart", True),  # ILIKE ignores case
    (QueryOperator.ENDS_WITH, "_v2", "chart_v2", True),
    (QueryOperator.ENDS_WITH, "_v2", "chartXv2", False),
    (QueryOperator.CONTAINS, "100%", "100% done", True),
    (QueryOperator.CONTAINS, "100%", "1000 done", False),
])
def test_wildcards_in_the_value_match_literally(operator, value, name, matches):
    query_filter = text_filter(operator, value)

    assert query_filter.wildcard_columns == ["slice_name"]
    assert query_filter.matches({"slice_name": name}) is matches


def test_values_without_wildcards_and_other_operators_are_left_to_the_server():
    query_filter = text_filter(QueryOperator.STARTS_WITH, "plain")
    query_filter.add("slice_name", QueryOperator.NOT_STARTS_WITH, "a_b")
    query_filter.add("owners.first_name", QueryOperator.STARTS_WITH, "a_b")  # a related column is not listed

    assert query_filter.wildcard_columns == []
    assert query_filter.matches({"slice_name": "anything"})

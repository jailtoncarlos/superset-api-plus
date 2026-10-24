"""Databases, datasets, saved queries and listing operators on the real Superset."""
import pytest

from supersetapiplus.databases import Database
from supersetapiplus.exceptions import BadRequestError, NotFound
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.saved_queries import SavedQuery

from .conftest import unique_name


def test_database_created_and_read(client, database):
    assert client.databases.get(database.id).database_name == database.database_name


def test_database_with_invalid_uri_is_rejected(client):
    with pytest.raises(BadRequestError):
        client.databases.add(Database(database_name=unique_name("db-invalid"), sqlalchemy_uri="not-a-uri"))


def test_dataset_created_updated_and_read(client, dataset):
    fetched = client.datasets.get(dataset.id)
    fetched.description = "changed by the tests"
    fetched.save()

    assert client.datasets.get(dataset.id).description == "changed by the tests"


def test_get_datasource_by_table_name(client, dataset):
    datasource = client.datasets.get_datasource(dataset.table_name)

    assert (datasource.id, str(datasource.type)) == (dataset.id, "table")
    with pytest.raises(NotFound):
        client.datasets.get_datasource(unique_name("missing"))


def test_saved_query_created_and_deleted(client, database):
    saved_query = SavedQuery(label=unique_name("sq"), sql="select 1", db_id=database.id, schema="public")

    client.saved_queries.add(saved_query)
    try:
        assert client.saved_queries.get(saved_query.id).label == saved_query.label
    finally:
        assert client.saved_queries.delete(saved_query.id)


# --- Listing operators ----------------------------------------------------------------------

def test_library_operators_are_accepted_by_the_server(client):
    filters = client.get(client.join_urls(client.charts.base_url, "_info"), params={"q": "(keys:!(filters))"}).json()
    accepted = {op["operator"] for column in filters["filters"].values() for op in column}

    assert {op.value for op in QueryOperator} <= accepted


def test_listing_operators_select_the_expected_charts(client, add_chart):
    table, pie = add_chart("table"), add_chart("pie")
    ids = [table.id, pie.id]

    def found(column: str, operator: QueryOperator, value) -> set[int]:
        query_filter = QueryStringFilter()
        query_filter.add("id", QueryOperator.IN, ids)
        query_filter.add(column, operator, value)
        return {c.id for c in client.charts.find(query_filter, columns=["id"])}

    assert found("viz_type", QueryOperator.EQUAL, "pie") == {pie.id}
    assert found("viz_type", QueryOperator.NOT_EQUAL, "pie") == {table.id}
    assert found("viz_type", QueryOperator.IN, ["table", "pie"]) == {table.id, pie.id}
    assert found("slice_name", QueryOperator.STARTS_WITH, table.slice_name) == {table.id}
    assert found("slice_name", QueryOperator.CONTAINS, pie.slice_name[-6:]) == {pie.id}

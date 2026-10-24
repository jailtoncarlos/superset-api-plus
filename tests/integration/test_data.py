"""Databases, datasets, saved queries, SQL Lab, listing operators, assets and log masking, on the real Superset."""
import logging
import os
import zipfile

import pytest

from supersetapiplus.databases import Database
from supersetapiplus.exceptions import BadRequestError, NotFound, QueryLimitReached, UnauthorizedError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.saved_queries import SavedQuery

from .conftest import PASSWORD, new_client, only_test_stack, unique_name


# --- Database, dataset and saved query ------------------------------------------------------

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


# --- SQL Lab -------------------------------------------------------------------------------

def test_runs_sql_through_the_database(client, database):
    columns, data = client.databases.get(database.id).run("select 1 as one")

    assert data == [{"one": 1}] and [c["name"] for c in columns] == ["one"]


def test_client_run_sends_schema_and_limit(client, database):
    columns, data = client.run(database_id=database.id, query="select 1 as one union all select 2", query_limit=5,
                               schema="public")

    assert sorted(row["one"] for row in data) == [1, 2]


def test_result_beyond_the_query_limit_is_reported(client, database):
    with pytest.raises(QueryLimitReached):
        client.run(database_id=database.id, query="select generate_series(1, 10) as n", query_limit=3)


# --- Listing filters ------------------------------------------------------------------------

def test_library_operators_are_accepted_by_the_server(client):
    filters = client.get(client.join_urls(client.charts.base_url, "_info"), params={"q": "(keys:!(filters))"}).json()
    accepted = {op["operator"] for column in filters["filters"].values() for op in column}

    assert {op.value for op in QueryOperator} <= accepted


@pytest.mark.parametrize("operator,value", [(QueryOperator.NOT_EQUAL, "x"), (QueryOperator.CONTAINS, "zz"),
                                            (QueryOperator.STARTS_WITH, "zz"), (QueryOperator.IN, ["table"])])
def test_listing_with_operators_responds_without_error(client, operator, value):
    query_filter = QueryStringFilter()
    column = "viz_type" if operator in (QueryOperator.IN, QueryOperator.NOT_EQUAL) else "slice_name"
    query_filter.add(column, operator, value)

    assert client.charts.count(query_filter) >= 0


# --- Assets --------------------------------------------------------------------------------

@only_test_stack
def test_assets_export_and_import_from_the_given_path(client, database, add_chart, tmp_path):
    add_chart()
    archive = tmp_path / "subdir" / "assets.zip"
    archive.parent.mkdir()

    client.assets.export(archive)
    with zipfile.ZipFile(archive) as content:
        databases = [n.split("/", 1)[1] for n in content.namelist() if "/databases/" in n]

    # Exported database URIs have the password masked; the import asks for it per database file.
    passwords = {name: os.environ["POSTGRES_PASSWORD"] for name in databases} if databases else None
    assert client.assets.import_file(archive, passwords=passwords) is True


# --- Log masking ---------------------------------------------------------------------------

def test_http_error_logs_do_not_expose_password_token_or_cookie(client, caplog):
    session_client, jwt_client = new_client(), new_client(session_mode=False)
    jwt_client.charts.count()
    cookie, csrf = session_client.session.cookies.get("session"), session_client.session.headers["X-CSRFToken"]
    caplog.set_level(logging.DEBUG, logger="supersetapiplus")

    with pytest.raises(UnauthorizedError):
        new_client(session_mode=False, password=f"{PASSWORD}-wrong").charts.count()
    for logged_client in (session_client, jwt_client):
        with pytest.raises(BadRequestError):
            logged_client.charts.get(2_000_000_000)

    assert caplog.records, "the errors should have been logged"
    for secret in (f"{PASSWORD}-wrong", cookie, csrf, jwt_client._access_token, jwt_client._refresh_token):
        assert secret not in caplog.text

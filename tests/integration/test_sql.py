"""SQL Lab (POST /api/v1/sqllab/execute/) on the real Superset."""
import pytest

from supersetapiplus.exceptions import QueryLimitReached


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

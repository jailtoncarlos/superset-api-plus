"""Soft delete of Superset 7.0 (SOFT_DELETE, on by default): a deleted chart, dashboard or dataset is archived,
listed by find_archived, restored or purged by its uuid. Skipped on a server before 7.0."""
import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import BadRequestError, NotFound, ResourceNotFoundError, UnprocessableEntityError

from .conftest import name_filter, new_chart, unique_name
from .server_version import is_superset_7

# A physical table every PostgreSQL has (get_or_create takes physical tables only).
SCHEMA, TABLE = "information_schema", "sql_features"


@pytest.fixture(autouse=True)
def superset_7(client):
    if not is_superset_7(client):
        pytest.skip(f"Superset {client.server_version or '(unknown version)'} has no soft delete (7.0)")


def archived_named(repository, column: str, name: str) -> list:
    return repository.find_archived(name_filter(column, name))


@pytest.mark.parametrize("kind", ["chart", "dashboard"])
def test_a_deleted_object_is_archived_restored_and_purged(client, dataset, cleanup, kind):
    if kind == "chart":
        repository, column, obj = client.charts, "slice_name", new_chart("table", dataset)
        name = obj.slice_name
        cleanup.chart(repository.add(obj))
    else:
        repository, column = client.dashboards, "dashboard_title"
        obj = Dashboard(dashboard_title=unique_name("dash"))
        name = obj.dashboard_title
        cleanup.dashboard(repository.add(obj))

    assert repository.delete(obj.id)
    with pytest.raises((NotFound, ResourceNotFoundError)):
        repository.get(obj.id)
    (archived,) = archived_named(repository, column, name)
    assert archived.id == obj.id and archived.uuid

    repository.restore(archived.uuid)
    assert repository.get(obj.id).id == obj.id and archived_named(repository, column, name) == []

    repository.delete(obj.id)
    repository.purge(archived.uuid)
    assert archived_named(repository, column, name) == []
    with pytest.raises(BadRequestError):
        repository.restore(archived.uuid)  # gone for good


def test_an_archived_dataset_is_purged_with_its_impact_token_and_get_or_create_names_the_hidden_twin(client,
                                                                                                     database):
    """get_or_create of a physical table whose dataset is archived: Superset refuses (422) naming the archived twin
    and its restore route, instead of creating a second dataset."""
    table = client.datasets.get_or_create(TABLE, database, schema=SCHEMA)
    assert client.datasets.delete(table.id)
    (archived,) = [d for d in client.datasets.find_archived(name_filter("table_name", TABLE))
                   if d.id == table.id]
    try:
        with pytest.raises(UnprocessableEntityError, match="restore"):
            client.datasets.get_or_create(TABLE, database, schema=SCHEMA)
    finally:
        client.datasets.purge(archived.uuid)
    assert [d for d in client.datasets.find_archived(name_filter("table_name", TABLE)) if d.id == table.id] == []

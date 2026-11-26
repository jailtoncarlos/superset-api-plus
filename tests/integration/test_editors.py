"""Editors and viewers of charts, dashboards and datasets (Superset 7.0): subjects, sent as ids and read as objects;
`owners` (users) and dashboard `roles` are deprecated aliases turned into subjects. Skipped on a server before 7.0.
Viewers need the ENABLE_VIEWERS feature flag, on in the test stack (docker/superset/superset_config.py)."""
import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.datasets import Dataset

from .conftest import SQL_DATASET, new_chart, unique_name
from .server_version import is_superset_7


@pytest.fixture
def me(client):
    if not is_superset_7(client):
        pytest.skip(f"Superset {client.server_version or '(unknown version)'} has no editors (7.0)")
    user_id = client.get(client.join_urls(client.base_url, "me/")).json()["result"]["id"]
    return user_id, client.subjects.for_user(user_id).id


def editor_ids(obj) -> list:
    return [editor["id"] for editor in obj.editors]


def test_owners_given_as_users_become_the_editors_of_a_new_chart_dashboard_and_dataset(client, dataset, database,
                                                                                         cleanup, me):
    user_id, subject_id = me
    chart = new_chart("table", dataset)
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    new_dataset = Dataset(table_name=unique_name("ds"), schema="public", sql=SQL_DATASET, database_id=database.id)
    for obj, repository, register in ((chart, client.charts, cleanup.chart), (dashboard, client.dashboards,
                                      cleanup.dashboard), (new_dataset, client.datasets, cleanup.dataset)):
        obj.owners = [user_id]
        with pytest.warns(DeprecationWarning, match="owners is deprecated since Superset 7.0: use editors"):
            register(repository.add(obj))

        assert editor_ids(repository.get(obj.id)) == [subject_id], type(obj).__name__


def test_editors_read_back_are_saved_unchanged(client, add_chart, me):
    _, subject_id = me
    chart = add_chart()
    stored = client.charts.get(chart.id)
    assert editor_ids(stored) == [subject_id]  # Superset makes the creator an editor

    stored.description = "saved back"
    stored.save()

    again = client.charts.get(chart.id)
    assert (editor_ids(again), again.description) == ([subject_id], "saved back")


def test_dashboard_roles_become_viewers_and_chart_viewers_are_saved(client, add_chart, cleanup, me):
    roles = client.get(client.join_urls(client.base_url, "security/roles/"), params={"q": "(page_size:100)"}).json()
    gamma = next(role["id"] for role in roles["result"] if role["name"] == "Gamma")
    alpha = next(role["id"] for role in roles["result"] if role["name"] == "Alpha")
    gamma_subject, alpha_subject = client.subjects.for_role(gamma).id, client.subjects.for_role(alpha).id
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    cleanup.dashboard(client.dashboards.add(dashboard))
    dashboard.roles = [gamma]
    with pytest.warns(DeprecationWarning, match="roles is deprecated since Superset 7.0: use viewers"):
        dashboard.save()
    assert [viewer["id"] for viewer in client.dashboards.get(dashboard.id).viewers] == [gamma_subject]
    dashboard.roles = [alpha]  # replacing the roles, as on Superset 6.1, revokes Gamma
    with pytest.warns(DeprecationWarning):
        dashboard.save()
    assert [viewer["id"] for viewer in client.dashboards.get(dashboard.id).viewers] == [alpha_subject]
    dashboard.roles = []  # clearing the roles, as on Superset 6.1, clears the viewers
    with pytest.warns(DeprecationWarning):
        dashboard.save()
    assert client.dashboards.get(dashboard.id).viewers == []

    chart = add_chart()
    chart.viewers = [gamma_subject]
    chart.save()
    stored = client.charts.get(chart.id)
    assert [viewer["id"] for viewer in stored.viewers] == [gamma_subject]
    stored.description = "saved back"
    stored.save()  # viewers read as objects are sent back as ids
    assert [viewer["id"] for viewer in client.charts.get(chart.id).viewers] == [gamma_subject]


def test_viewers_reloaded_with_fetch_are_revoked_by_a_deprecated_alias(client, cleanup, me):
    """The viewers changed on the server after reading, reloaded with fetch(), are what Superset has: roles = []
    clears them (not kept as if the code had assigned them)."""
    roles = client.get(client.join_urls(client.base_url, "security/roles/"), params={"q": "(page_size:100)"}).json()
    gamma = next(role["id"] for role in roles["result"] if role["name"] == "Gamma")
    alpha = next(role["id"] for role in roles["result"] if role["name"] == "Alpha")
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    cleanup.dashboard(client.dashboards.add(dashboard))
    dashboard.viewers = [client.subjects.for_role(gamma).id]
    dashboard.save()
    loaded = client.dashboards.get(dashboard.id)

    other = client.dashboards.get(dashboard.id)  # another session adds Alpha
    other.viewers = [viewer["id"] for viewer in other.viewers] + [client.subjects.for_role(alpha).id]
    other.save()
    loaded.fetch()
    assert len(loaded.viewers) == 2

    loaded.roles = []
    with pytest.warns(DeprecationWarning):
        loaded.save()
    assert client.dashboards.get(dashboard.id).viewers == []

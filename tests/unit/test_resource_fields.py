"""Fields of the REST resources added for Superset 6.1.0 (DashboardRestApi, DatasetRestApi, DatabaseRestApi)."""
import json
import warnings
from types import SimpleNamespace

import pytest

from supersetapiplus.charts.table import TableChart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.resources.repository import _resolve_subject_aliases


def test_editors_and_viewers_read_as_objects_are_sent_as_ids_and_kept_as_read():
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}", "json_metadata": "{}",
                                     "editors": [{"id": 3, "label": "Ann", "type": 1}],
                                     "viewers": [{"id": 4, "label": "Gamma", "type": 2}]})

    assert (dashboard.to_json()["editors"], dashboard.to_json()["viewers"]) == ([3], [4])
    assert dashboard.editors == [{"id": 3, "label": "Ann", "type": 1}]


def test_dashboard_roles_is_a_deprecated_alias_of_viewers():
    dashboard = Dashboard(dashboard_title="P")
    dashboard.roles = [4]

    with pytest.warns(DeprecationWarning, match="Dashboard.roles is deprecated since Superset 7.0: use viewers"):
        _resolve_subject_aliases(dashboard, FakeSubjects())

    assert (dashboard.viewers, dashboard.roles) == ([204], None)
    assert "roles" not in Dashboard.POST_FIELDS + Dashboard.PUT_FIELDS


def test_a_deprecated_alias_replaces_the_subjects_read_as_assigning_it_did_on_superset_6_1():
    """Viewers of roles 4 and 5 read; roles = [5] revokes role 4, as it did on 6.1 (not kept granted)."""
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}", "json_metadata": "{}",
                                     "editors": [{"id": 101}], "viewers": [{"id": 204}, {"id": 205}]})
    dashboard.roles, dashboard.owners = [5], [2]
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert (dashboard.viewers, dashboard.editors) == ([205], [102])
    dashboard.roles = [6]  # replaced again: what the first resolution wrote is not kept as if set in code
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert dashboard.viewers == [206]


def test_subjects_assigned_or_changed_after_reading_are_kept_with_a_deprecated_alias():
    """viewers = [subject] with roles = [role] on a dashboard read with viewers: the assigned subject is not taken
    for the list read from Superset and dropped; the same for a list changed in place."""
    read = {"id": 1, "dashboard_title": "P", "position_json": "{}", "json_metadata": "{}",
            "editors": [{"id": 101}], "viewers": [{"id": 204}, {"id": 205}]}
    dashboard = Dashboard.from_json(read)
    dashboard.viewers, dashboard.roles = [300], [5]
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert dashboard.viewers == [300, 205]

    dashboard = Dashboard.from_json(read)
    dashboard.viewers, dashboard.roles = [204, 205], [6]  # the ids read, assigned again: kept too
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert dashboard.viewers == [204, 205, 206]

    dashboard = Dashboard.from_json(read)
    dashboard.editors.append(300)
    dashboard.owners = [2]
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert dashboard.editors == [101, 300, 102]


def test_an_empty_list_given_to_a_deprecated_alias_clears_the_subjects():
    """dashboard.roles = [] cleared the dashboard roles on Superset 6.1: it clears the viewers, not left granted."""
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}", "json_metadata": "{}",
                                     "editors": [{"id": 3}], "viewers": [{"id": 4}]})
    _resolve_subject_aliases(dashboard, FakeSubjects())
    assert (dashboard.editors, dashboard.viewers) == ([{"id": 3}], [{"id": 4}])  # aliases unset: nothing changes

    dashboard.roles, dashboard.owners = [], []
    with pytest.warns(DeprecationWarning):
        _resolve_subject_aliases(dashboard, FakeSubjects())
    assert (dashboard.editors, dashboard.viewers) == ([], [])
    assert dashboard.to_json(list(Dashboard.PUT_FIELDS))["viewers"] == []

    dashboard.viewers = [204]
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        _resolve_subject_aliases(dashboard, FakeSubjects())  # resolved once: a later save keeps the viewers
    assert dashboard.viewers == [204]


def test_new_dashboard_does_not_send_editors_so_superset_assigns_the_current_user():
    assert "editors" not in Dashboard(dashboard_title="P").to_json(columns=list(Dashboard.POST_FIELDS))


class FakeSubjects:
    """client.subjects stand-in: the subject of user n is 100 + n, of role n is 200 + n."""

    def for_user(self, user_id):
        return SimpleNamespace(id=100 + user_id)

    def for_role(self, role_id):
        return SimpleNamespace(id=200 + role_id)


NEW = {"chart": lambda: TableChart.instance(slice_name="C", datasource=DataSource(id=1, type="table")),
       "dashboard": lambda: Dashboard(dashboard_title="P"), "dataset": lambda: Dataset(table_name="t")}


@pytest.mark.parametrize("kind", list(NEW))
def test_owners_is_a_deprecated_alias_of_editors_turned_into_subjects(kind):
    obj = NEW[kind]()
    model = type(obj)
    obj.editors, obj.owners = [{"id": 101, "label": "Ann"}], [1, {"id": 2}, SimpleNamespace(id=3)]

    with pytest.warns(DeprecationWarning, match="owners is deprecated since Superset 7.0: use editors"):
        _resolve_subject_aliases(obj, FakeSubjects())

    assert (obj.editors, obj.owners) == ([101, 102, 103], None)  # subject 101 already there: kept once
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        _resolve_subject_aliases(obj, FakeSubjects())  # resolved once: nothing left to warn about
    assert "owners" not in model.POST_FIELDS + model.PUT_FIELDS and "editors" in model.POST_FIELDS


def test_dataset_metrics_are_sent_with_the_update_schema_keys_only():
    dataset = Dataset.from_json({"id": 1, "table_name": "t", "metrics": [
        {"id": 9, "metric_name": "count", "expression": "COUNT(*)", "changed_on": "2026-10-24", "created_on": "x"}]})
    dataset.add_metric("total", "SUM(total)", verbose_name="Total")

    assert dataset.to_json()["metrics"] == [{"id": 9, "metric_name": "count", "expression": "COUNT(*)"},
                                            {"metric_name": "total", "expression": "SUM(total)",
                                             "verbose_name": "Total"}]


def read_dataset() -> Dataset:
    return Dataset.from_json({"id": 1, "table_name": "t", "metrics": [
        {"id": 9, "metric_name": "total", "expression": "SUM(x)", "changed_on": "2026-10-24"}], "columns": [
        {"id": 4, "column_name": "campus", "type": "STRING", "changed_on": "x"},
        {"id": 5, "column_name": "double", "expression": "x * 2", "type": "INTEGER"}]})


def test_metric_and_calculated_column_with_an_existing_name_are_updated_keeping_the_id():
    dataset = read_dataset()

    dataset.add_metric("total", "SUM(y)", verbose_name="Total")
    dataset.add_calculated_column("double", "y * 2")
    dataset.add_calculated_column("triple", "y * 3", type="INTEGER")

    sent = dataset.to_json()
    assert sent["metrics"] == [{"id": 9, "metric_name": "total", "expression": "SUM(y)", "verbose_name": "Total"}]
    assert sent["columns"] == [{"id": 4, "column_name": "campus", "type": "STRING"},
                               {"id": 5, "column_name": "double", "expression": "y * 2", "type": "INTEGER"},
                               {"column_name": "triple", "expression": "y * 3", "type": "INTEGER"}]


def test_columns_are_not_sent_unless_changed_and_table_columns_are_not_replaced():
    dataset = read_dataset()
    assert "columns" not in dataset.to_json()

    with pytest.raises(ValidationError, match="is a column of the table"):
        dataset.add_calculated_column("campus", "upper(campus)")


@pytest.mark.parametrize("dataset", [
    Dataset(table_name="new"),                                  # not saved: POST does not take metrics
    Dataset(id=1, table_name="built in code"),                  # stored metrics unknown: a save deletes them
    Dataset.from_json({"id": 1, "table_name": "from find"}),     # list endpoint: no metrics or columns
])
def test_metrics_and_columns_are_changed_only_on_a_dataset_read_with_get(dataset):
    with pytest.raises(ValidationError, match="Read the dataset with client.datasets.get"):
        dataset.add_metric("total", "SUM(x)")
    with pytest.raises(ValidationError, match="Read the dataset with client.datasets.get"):
        dataset.add_calculated_column("double", "x * 2")


def test_removed_database_fields_warn_and_are_not_sent():
    with pytest.warns(DeprecationWarning):
        database = Database(database_name="db", encrypted_extra='{"secret": 1}')
    with pytest.warns(DeprecationWarning):
        Database(database_name="db", allow_multi_schema_metadata_fetch=True)

    payload = database.to_json(columns=list(Database.POST_FIELDS))
    assert payload["masked_encrypted_extra"] == '{"secret": 1}' and "encrypted_extra" not in payload


def test_database_read_from_superset_does_not_warn(recwarn):
    Database.from_json({"id": 9, "database_name": "dw", "sqlalchemy_uri": "postgresql://u:XXXXXXXXXX@h/db"})

    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def test_json_metadata_keys_of_superset_6_round_trip():
    metadata = {"color_namespace": "ns", "map_label_colors": {"North": "#fff"}, "positions": {},
                "filter_bar_orientation": "HORIZONTAL", "show_chart_timestamps": True,
                "chart_customization_config": [], "stagger_refresh": False, "stagger_time": 5}
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}",
                                     "json_metadata": json.dumps(metadata)})

    written = json.loads(dashboard.to_json()["json_metadata"])
    assert {key: written[key] for key in metadata} == metadata

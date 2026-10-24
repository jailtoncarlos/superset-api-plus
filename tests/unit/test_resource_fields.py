"""Fields of the REST resources added for Superset 6.1.0 (DashboardRestApi, DatasetRestApi, DatabaseRestApi)."""
import json

import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset


def test_owners_and_roles_read_as_objects_are_sent_as_ids_and_kept_as_read():
    dashboard = Dashboard.from_json({"id": 1, "dashboard_title": "P", "position_json": "{}", "json_metadata": "{}",
                                     "owners": [{"id": 3, "first_name": "A"}], "roles": [{"id": 4, "name": "Gamma"}]})

    assert (dashboard.to_json()["owners"], dashboard.to_json()["roles"]) == ([3], [4])
    assert dashboard.owners == [{"id": 3, "first_name": "A"}]


def test_new_dashboard_does_not_send_owners_so_superset_assigns_the_current_user():
    assert "owners" not in Dashboard(dashboard_title="P").to_json(columns=list(Dashboard.POST_FIELDS))


def test_dataset_metrics_are_sent_with_the_update_schema_keys_only():
    dataset = Dataset.from_json({"id": 1, "table_name": "t", "metrics": [
        {"id": 9, "metric_name": "count", "expression": "COUNT(*)", "changed_on": "2026-10-24", "created_on": "x"}]})
    dataset.add_metric("total", "SUM(total)", verbose_name="Total")

    assert dataset.to_json()["metrics"] == [{"id": 9, "metric_name": "count", "expression": "COUNT(*)"},
                                            {"metric_name": "total", "expression": "SUM(total)",
                                             "verbose_name": "Total"}]


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

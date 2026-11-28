"""Themes (supersetapiplus.resources.themes) and the dashboard theme binding: the checks the 6.1.0 backend makes
(superset/themes/schemas.py, utils.py), the ECharts override tokens and the lossless theme_id. Pure logic, no HTTP."""
import json

import pytest

from supersetapiplus import Dashboard, Theme
from supersetapiplus.core.types import ThemeAlgorithm
from supersetapiplus.exceptions import UnsupportedTypeError, ValidationError

BAR_LABELS = {"echarts_timeseries_bar": {"series": {"label": {"show": True, "position": "inside"}}}}


def test_echarts_overrides_are_tokens_of_the_configuration_and_keep_the_rest():
    theme = Theme(theme_name="Panel")
    theme.set_config({"token": {"colorPrimary": "#1677ff"}, "algorithm": "dark"})

    theme.set_echarts_overrides(all_charts={"legend": {"show": False}}, by_chart_type=BAR_LABELS)

    assert theme.config == {"algorithm": "dark", "token": {
        "colorPrimary": "#1677ff", "echartsOptionsOverrides": {"legend": {"show": False}},
        "echartsOptionsOverridesByChartType": BAR_LABELS}}
    theme.validate()


def test_none_keeps_an_override_and_an_empty_mapping_removes_it():
    theme = Theme(theme_name="Panel")
    theme.set_echarts_overrides(all_charts={"legend": {"show": False}}, by_chart_type=BAR_LABELS)

    theme.set_echarts_overrides(by_chart_type={})

    assert theme.config["token"] == {"echartsOptionsOverrides": {"legend": {"show": False}}}


def test_functions_cannot_be_stored_in_a_theme():
    with pytest.raises(ValidationError, match="not JSON"):
        Theme(theme_name="Panel").set_echarts_overrides(all_charts={"tooltip": {"formatter": print}})


@pytest.mark.parametrize("config, message", [
    ([], "must be an object"), ({"token": []}, r"\['token'\] have the wrong type"),
    ({"hashed": "yes"}, "wrong type"), ({"algorithm": "sepia"}, "not accepted"),
    ({"algorithm": ["dark", "system"]}, "not accepted")])
def test_configurations_the_backend_rejects_are_rejected_before_the_request(config, message):
    with pytest.raises(ValidationError, match=message):
        Theme(theme_name="Panel").set_config(config)


def test_accepted_algorithms_are_the_theme_modes():
    theme = Theme(theme_name="Panel")
    for algorithm in ("system", ["dark", "compact"], *(mode.value for mode in ThemeAlgorithm)):
        theme.set_config({"algorithm": algorithm})


def test_a_theme_built_in_code_needs_a_name_and_a_json_object():
    with pytest.raises(ValidationError, match="name cannot be empty"):
        Theme(theme_name=" ").validate()
    with pytest.raises(ValidationError, match="JSON text of an object"):
        Theme(theme_name="Panel", json_data="{token: {}}").validate()


def test_a_theme_read_from_superset_is_written_back_as_read():
    stored = {"id": 3, "theme_name": "Old", "json_data": '{"token":{"x":1}, "algorithm": "sepia"}', "uuid": "u",
              "is_system": False, "is_system_default": False, "is_system_dark": False}
    theme = Theme.from_json(stored)

    assert theme.to_json(columns=list(Theme.PUT_FIELDS)) == {"theme_name": "Old", "json_data": stored["json_data"]}


def read_dashboard(**fields) -> Dashboard:
    return Dashboard.from_json({"id": 5, "dashboard_title": "Panel", "json_metadata": "{}", **fields})


def put_payload(dashboard: Dashboard) -> dict:
    return dashboard.to_json(columns=list(Dashboard.PUT_FIELDS))


def test_the_bound_theme_is_read_from_the_theme_object_and_written_back_as_theme_id():
    dashboard = read_dashboard(theme={"id": 7, "theme_name": "Bars", "json_data": "{}"})

    assert dashboard.theme_id == 7 and put_payload(dashboard)["theme_id"] == 7


@pytest.mark.parametrize("fields", [{}, {"theme": None}])
def test_a_dashboard_without_theme_does_not_send_theme_id(fields):
    """A save never unbinds a theme chosen in the UI meanwhile: without set_theme, theme_id is not sent."""
    assert "theme_id" not in put_payload(read_dashboard(**fields))
    assert "theme_id" not in Dashboard(dashboard_title="New").to_json()


def test_set_theme_binds_by_theme_or_id_and_none_sends_null():
    dashboard = read_dashboard(theme={"id": 7, "theme_name": "Bars"})

    dashboard.set_theme(Theme(theme_name="Other", id=9))
    assert put_payload(dashboard)["theme_id"] == 9
    dashboard.set_theme(4)
    assert put_payload(dashboard)["theme_id"] == 4
    dashboard.set_theme(None)
    assert put_payload(dashboard)["theme_id"] is None
    assert json.loads(json.dumps(put_payload(dashboard)))["theme_id"] is None


def test_a_theme_must_be_saved_before_it_is_bound():
    with pytest.raises(UnsupportedTypeError, match="save it first"):
        Dashboard(dashboard_title="New").set_theme(Theme(theme_name="Unsaved"))

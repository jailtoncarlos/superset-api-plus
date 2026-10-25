"""Defects found by typing the public API (issue: fully typed public API): inputs a type now names explicitly.

The parameters typed Any hid cases where a value could be missing: a chart not saved yet (id None), a histogram
without its column, a pie without its metric. Each case used to raise an unrelated error or write a wrong value.
"""
import pytest

from supersetapiplus.charts import build_query as bq
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout import ChartRef
from supersetapiplus.dashboards.metadata import Metadata
from supersetapiplus.exceptions import ChartValidationError
from supersetapiplus.services.dashboard_charts import DashboardCharts

BASE = {"datasource": "7__table", "adhoc_filters": [], "extra_form_data": {}}


class Unsaved:
    """A chart reference without an id (a SavedChart not saved yet)."""
    id = None
    slice_name = "Not saved"


def test_cross_filter_configuration_rejects_a_chart_without_id():
    metadata = Metadata()

    with pytest.raises(ValueError, match="not saved"):
        metadata.add_chart(Unsaved())

    assert metadata.global_chart_configuration.chartsInScope == []  # None was appended before


def test_a_saved_chart_reference_can_be_placed_but_only_a_library_chart_can_be_created():
    service = DashboardCharts(client=None)  # the checks run before any request
    dashboard = Dashboard(dashboard_title="D", id=1)

    with pytest.raises(ChartValidationError, match="Only a library Chart can be created"):
        service.add_chart(dashboard, Unsaved(), "Title")


def test_histogram_without_its_column_has_no_column_label_instead_of_failing():
    (query,) = bq.query_context_for({**BASE, "viz_type": "histogram_v2"})["queries"]  # AttributeError before

    assert "column" not in query["post_processing"][0]["options"]


def test_pie_without_its_metric_builds_a_query_instead_of_failing():
    context = bq.query_context_for({**BASE, "viz_type": "pie", "groupby": ["region"]})  # AttributeError before

    assert context["queries"][0]["columns"] == ["region"]


def test_a_chart_ref_is_a_saved_chart_for_the_layout():
    dashboard = Dashboard(dashboard_title="D")

    component = dashboard.position_json.add_chart(ChartRef(5, "Saved chart"), parent=dashboard.position_json.add_row())

    assert component.meta["chartId"] == 5 and dashboard.position_json.remove_chart(Unsaved()) == 0

"""Example dashboard 'Featured Charts': round trip, chart copies and dashboard copy (see checks.py)."""
import pytest

from supersetapiplus.charts import charts

from ..conftest import unique_name
from .checks import ExampleDashboardChecks


class TestFeaturedCharts(ExampleDashboardChecks):
    TITLE = 'Featured Charts'

    def test_data_comparison_detects_a_shared_query_builder_regression(self, client, modeled, removal, monkeypatch):
        """A wrong row limit in both library query paths must not change the independent reference."""
        chart_id = next(pk for pk, chart in modeled.items() if chart.slice_name == "Table")
        build = charts.query_context_for

        def wrong_row_limit(form_data):
            context = build(form_data)
            context["queries"][0]["row_limit"] = 1
            return context

        monkeypatch.setattr(charts, "query_context_for", wrong_row_limit)
        chart = client.charts.get(chart_id)
        chart.id, chart.slice_name = None, unique_name("wrong-example-query")
        chart.derive_query_context()
        copy_id = removal.chart(client.charts.add(chart))

        with pytest.raises(AssertionError, match="data differs from the original"):
            self.test_chart_copies_keep_the_params_and_return_the_data_of_the_original(
                client, {chart_id: modeled[chart_id]}, {chart_id: copy_id})

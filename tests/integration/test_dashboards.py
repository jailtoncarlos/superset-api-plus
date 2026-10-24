"""Dashboards against the real Superset: writing, chart association, layout and native filters."""
import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.native_filters import FilterType
from supersetapiplus.exceptions import DashboardValidationError, NotFound, ResourceNotFoundError
from supersetapiplus.query_string import QueryOperator

from .conftest import name_filter, new_chart, unique_name


@pytest.fixture
def add_dashboard(client, cleanup):
    def create(title: str | None = None) -> Dashboard:
        dashboard = Dashboard(dashboard_title=title or unique_name("dash"))
        cleanup.dashboard(client.dashboards.add(dashboard))
        return dashboard
    return create


def charts_named(client, prefix: str) -> int:
    return client.charts.count(name_filter("slice_name", prefix, QueryOperator.STARTS_WITH))


def test_dashboard_created_read_updated_and_deleted(client, add_dashboard):
    dashboard = add_dashboard()

    fetched = client.dashboards.get(dashboard.id)
    assert fetched.position_json.to_dict() == dashboard.position_json.to_dict()
    assert fetched.json_metadata.to_dict() == dashboard.json_metadata.to_dict()
    fetched.dashboard_title = f"{dashboard.dashboard_title}-changed"
    fetched.save()
    assert client.dashboards.get(dashboard.id).dashboard_title.endswith("-changed")

    assert client.dashboards.delete(dashboard.id) is True
    with pytest.raises(ResourceNotFoundError):
        client.dashboards.get(dashboard.id)


def test_add_to_dashboard_appends_and_does_not_duplicate(client, add_chart, add_dashboard):
    chart, first, second = add_chart(), add_dashboard(), add_dashboard()

    client.charts.add_to_dashboard(chart, first.id)
    client.charts.add_to_dashboard(chart, second.id)
    client.charts.add_to_dashboard(chart, second.id)

    assert sorted(client.charts.dashboard_ids(chart.id)) == sorted([first.id, second.id])


def test_attach_charts_associates_every_chart_in_the_layout(client, add_chart, add_dashboard):
    charts, dashboard = [add_chart(), add_chart("pie")], add_dashboard()
    tab = dashboard.position.add_tab("Tab")
    for chart in charts:
        dashboard.position.add_chart(chart, chart.slice_name, parent=tab)
    dashboard.save()

    assert client.dashboards.attach_charts(dashboard) == [c.id for c in charts]
    assert sorted(c.id for c in client.dashboards.get(dashboard.id).get_charts()) == sorted(c.id for c in charts)


def test_add_chart_requires_a_saved_dashboard_before_creating_anything(client, dataset):
    dashboard = client.dashboards.get_base_object()(dashboard_title=unique_name("unsaved"))
    dashboard._factory = client.dashboards
    prefix = unique_name("orphan")

    with pytest.raises(DashboardValidationError):
        dashboard.add_chart(new_chart("table", dataset, prefix), "Title")
    assert charts_named(client, prefix) == 0


def test_add_chart_creates_places_and_associates(client, dataset, add_dashboard, cleanup):
    dashboard = add_dashboard()
    chart = new_chart("table", dataset)

    try:
        dashboard.add_chart(chart, "Title on the dashboard")
    finally:
        if chart.id:  # created even if a later step failed
            cleanup.chart(chart.id)
    dashboard.save()

    stored = client.dashboards.get(dashboard.id)
    assert stored.position_json.chart_ids() == [chart.id]
    assert client.charts.dashboard_ids(chart.id) == [dashboard.id]


def test_get_charts_tolerates_an_unmodeled_viz_type(client, add_chart, add_dashboard, unmodeled_chart):
    chart, dashboard = add_chart(), add_dashboard()
    for chart_id in (chart.id, unmodeled_chart):
        client.charts.add_to_dashboard(chart_id, dashboard.id)

    charts = {getattr(c, "id", None): c for c in client.dashboards.get(dashboard.id).get_charts()}

    assert type(charts[chart.id]).__name__ == "TableChart"
    assert type(charts[unmodeled_chart]).__name__ == "UnsupportedObject"


def test_delete_with_exclude_charts_removes_the_charts(client, add_chart, add_dashboard):
    chart, dashboard = add_chart(), add_dashboard()
    client.charts.add_to_dashboard(chart, dashboard.id)

    assert client.dashboards.get(dashboard.id).delete(exclude_charts=True) is True
    for factory, pk in ((client.dashboards, dashboard.id), (client.charts, chart.id)):
        with pytest.raises(ResourceNotFoundError):
            factory.get(pk)


def test_get_chart_data_checks_the_dashboard(client, add_chart, add_dashboard):
    chart, own, other = add_chart(), add_dashboard(), add_dashboard()
    client.charts.add_to_dashboard(chart, own.id)

    assert client.charts.get_chart_data(chart.id, dashboard_id=own.id)[0]["rowcount"] == 2
    with pytest.raises(NotFound):
        client.charts.get_chart_data(chart.id, dashboard_id=other.id)


def test_add_and_attach_validates_before_creating_the_chart(client, dataset):
    prefix = unique_name("orphan")

    with pytest.raises(DashboardValidationError):
        client.charts.add_and_attach_to_dashboard(new_chart("table", dataset, prefix), "Title")
    assert charts_named(client, prefix) == 0


def test_dashboard_layout_and_native_filters_are_stored_as_built(client, dataset, add_chart, add_dashboard):
    chart, dashboard = add_chart(), add_dashboard()
    pos = dashboard.reset_layout()
    tab = pos.add_tab("Overview", parent=pos.add_tabs())
    pos.add_markdown("## Section", parent=pos.add_row(parent=tab), height=None, width=12)
    pos.add_chart(chart, title="Renamed", parent=pos.add_row(parent=tab), width=6, id="CHART-main")
    meta = dashboard.json_metadata
    meta.clear_native_filters()
    meta.add_filter_divider("Section", "Filters of the section")
    parent = meta.add_native_filter("Campus", dataset, "campus")
    meta.add_native_filter("Campus again", dataset, "campus", parent=[parent], inverseSelection=True)
    dashboard.save()
    client.dashboards.attach_charts(dashboard)

    stored = client.dashboards.get(dashboard.id)
    assert stored.position_json.to_dict() == dashboard.position_json.to_dict()
    assert stored.json_metadata.native_filter_configuration == dashboard.json_metadata.native_filter_configuration
    assert stored.json_metadata.native_filter_configuration[1]["chartsInScope"] == [chart.id]
    assert [c.id for c in stored.get_charts()] == [chart.id]


def test_time_filter_without_dataset_and_chart_scoped_filter_are_stored(client, dataset, add_chart, add_dashboard):
    first, second, dashboard = add_chart(), add_chart("pie"), add_dashboard()
    pos = dashboard.reset_layout()
    row = pos.add_row()
    for chart in (first, second):
        pos.add_chart(chart, parent=row, width=6)
    meta = dashboard.json_metadata
    meta.clear_native_filters()
    meta.add_native_filter("Period", filter_type=FilterType.TIME)
    meta.add_native_filter("Campus", dataset, "campus", charts=[first])
    dashboard.save()

    period, campus = client.dashboards.get(dashboard.id).json_metadata.native_filter_configuration
    assert period["targets"] == [{}] and period["filterType"] == "filter_time"
    assert campus["scope"] == {"rootPath": ["ROOT_ID"], "excluded": [second.id]}
    assert campus["chartsInScope"] == [first.id]

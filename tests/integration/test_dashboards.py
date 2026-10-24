"""Dashboards against the real Superset: writing, chart association, layout and native filters."""
import pytest

from supersetapiplus.charts.build_query import query_context_for
from supersetapiplus.charts.charts import Chart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.datasets import Dataset
from supersetapiplus.dashboards.native_filters import FilterType
from supersetapiplus.exceptions import DashboardValidationError, NotFound, ResourceNotFoundError
from supersetapiplus.query_string import QueryOperator

from .conftest import URL, name_filter, new_chart, unique_name


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


def test_default_value_of_a_select_filter_filters_the_charts_when_the_dashboard_opens(
        client, dataset, add_chart, add_dashboard):
    chart, dashboard = add_chart(), add_dashboard()
    dashboard.reset_layout().add_chart(chart, width=12)
    meta = dashboard.json_metadata
    meta.clear_native_filters()
    meta.add_native_filter("Campus", client.datasets.get(dataset.id), "campus", default_value=["North"])
    dashboard.save()
    client.dashboards.attach_charts(dashboard)

    (stored,) = client.dashboards.get(dashboard.id).json_metadata.native_filter_configuration
    assert stored["defaultDataMask"]["filterState"] == {"value": ["North"], "label": "North",
                                                        "excludeFilterValues": True}
    # The dashboard applies the data mask to each chart in scope as extra_form_data of its form data.
    form_data = {**client.charts.get(chart.id).params.to_dict(), "dashboardId": dashboard.id,
                 "extra_form_data": stored["defaultDataMask"]["extraFormData"]}
    (result,) = client.post(client.join_urls(client.charts.base_url, "data"),
                            json=query_context_for(form_data)).json()["result"]
    assert [row["campus"] for row in result["data"]] == ["North"]
    assert {"column": "campus"} in result["applied_filters"] and result["rejected_filters"] == []


def test_native_filter_problems_report_a_column_missing_from_a_chart_dataset(client, database, dataset, add_chart,
                                                                            add_dashboard, cleanup):
    other = Dataset(table_name=unique_name("ds-no-campus"), schema="public", sql="select 5 as total",
                    database_id=database.id)
    cleanup.dataset(client.datasets.add(other))
    foreign = Chart.get_class("table", "supersetapiplus.charts.table").instance(
        slice_name=unique_name("table"), datasource=DataSource(id=other.id, type="table"))
    foreign.add_simple_metric("count")
    cleanup.chart(client.charts.add(foreign))
    chart, dashboard = add_chart(), add_dashboard()
    row = dashboard.reset_layout().add_row()
    for placed in (chart, foreign):
        dashboard.position.add_chart(placed, parent=row, width=6)
    dashboard.json_metadata.clear_native_filters()
    dashboard.json_metadata.add_native_filter("Campus", dataset, "campus")
    dashboard.save()
    client.dashboards.attach_charts(dashboard)

    assert client.dashboard_charts.native_filter_problems(dashboard) == [
        f"Filter 'Campus': column 'campus' is not in dataset {other.id} of chart {foreign.id}."]


def test_owners_and_roles_are_saved_as_ids_and_read_as_objects(client, add_dashboard):
    me = client.get(client.join_urls(URL, "api/v1/me/")).json()["result"]["id"]
    roles = client.get(client.join_urls(URL, "api/v1/security/roles/"), params={"q": "(page_size:100)"}).json()
    gamma = next(role["id"] for role in roles["result"] if role["name"] == "Gamma")
    dashboard = add_dashboard()
    dashboard.owners, dashboard.roles = [me], [gamma]
    dashboard.certified_by = "Data team"
    dashboard.save()

    stored = client.dashboards.get(dashboard.id)
    assert [o["id"] for o in stored.owners] == [me] and [r["id"] for r in stored.roles] == [gamma]
    assert stored.certified_by == "Data team"
    stored.dashboard_title += "-saved-back"
    stored.save()  # owners/roles read as objects are sent back as ids
    assert [r["id"] for r in client.dashboards.get(dashboard.id).roles] == [gamma]


def test_copy_and_delete_many(client, add_chart, add_dashboard, cleanup):
    chart, dashboard = add_chart(), add_dashboard()
    client.charts.add_to_dashboard(chart, dashboard.id)

    copy_id = cleanup.dashboard(client.dashboards.copy(dashboard, dashboard_title=f"{dashboard.dashboard_title}-copy"))
    copy = client.dashboards.get(copy_id)
    assert copy.dashboard_title.endswith("-copy") and copy_id != dashboard.id
    assert [c.id for c in copy.get_charts()] == [chart.id], "without duplicate_slices the copy shows the same charts"

    assert client.dashboards.delete_many([dashboard.id, copy_id]) is True
    for pk in (dashboard.id, copy_id):
        with pytest.raises(ResourceNotFoundError):
            client.dashboards.get(pk)


def test_dashboard_charts_service_associates_and_places(client, add_chart, add_dashboard):
    chart, dashboard = add_chart(), add_dashboard()

    client.dashboard_charts.add_chart(dashboard, chart, title="Via service", width=6)
    dashboard.save()

    stored = client.dashboards.get(dashboard.id)
    assert stored.position_json.chart_ids() == [chart.id]
    assert client.charts.dashboard_ids(chart.id) == [dashboard.id]

"""Chart <-> dashboard association, chart data, deletion and layout placement."""
import json

import pytest
import requests_mock as rm

from supersetapiplus.base.base import UnsupportedObject
from supersetapiplus.charts.table import TableChart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.itemposition import ItemPositionType, MarkdownItemPosition
from supersetapiplus.dashboards.metadataposition import Metadataposition
from supersetapiplus.exceptions import DashboardValidationError, NodePositionValidationError, NotFound

HOST = "https://superset.example"
API = f"{HOST}/api/v1"
PARAMS = {"datasource": "1__table", "viz_type": "table", "query_mode": "aggregate", "groupby": ["campus"],
          "metrics": ["count"]}


def chart_json(chart_id: int, dashboards=(), viz_type="table") -> dict:
    return {"id": chart_id, "slice_name": f"G{chart_id}", "viz_type": viz_type, "params": json.dumps(PARAMS),
            "query_context": None, "dashboards": [{"id": d, "dashboard_title": f"D{d}"} for d in dashboards]}


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "t"})
        m.get(f"{API}/security/csrf_token/", json={"result": "c"})
        m.get(f"{API}/chart/_info", json={})
        m.get(f"{API}/dashboard/_info", json={})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robot", "password")


def puts(mock, path):
    return [r.json() for r in mock.request_history if r.method == "PUT" and r.path == path]


def test_add_to_dashboard_appends_keeping_existing_associations(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[3])})
    mock.put(f"{API}/chart/9", json={"id": 9, "result": {}})

    assert client.charts.add_to_dashboard(9, 5) == [3, 5]
    assert puts(mock, "/api/v1/chart/9") == [{"dashboards": [3, 5]}]


def test_add_to_dashboard_already_associated_does_not_save_again(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[5])})

    assert client.charts.add_to_dashboard(9, 5) == [5]
    assert puts(mock, "/api/v1/chart/9") == []


def test_attach_charts_associates_every_chart_in_the_layout(client, mock):
    dashboard = Dashboard(dashboard_title="Panel", id=5)
    tab = dashboard.position.add_tab("Tab")
    for chart_id in (1, 2):
        dashboard.position.add_chart(TableChart(slice_name=f"G{chart_id}", id=chart_id), f"G{chart_id}", parent=tab)
        mock.get(f"{API}/chart/{chart_id}", json={"id": chart_id, "result": chart_json(chart_id)})
        mock.put(f"{API}/chart/{chart_id}", json={"result": {}})

    assert client.dashboards.attach_charts(dashboard) == [1, 2]
    assert puts(mock, "/api/v1/chart/1") == [{"dashboards": [5]}] and puts(mock, "/api/v1/chart/2") == [{"dashboards": [5]}]


def test_add_chart_requires_saved_dashboard_before_any_request(client, mock):
    dashboard = client.dashboards.get_base_object()(dashboard_title="New")
    dashboard._factory = client.dashboards

    with pytest.raises(DashboardValidationError):
        dashboard.add_chart(TableChart(slice_name="G", datasource_id=1), "G")
    assert [r for r in mock.request_history if r.method in ("POST", "PUT") and "/chart/" in r.path] == []


def test_add_chart_creates_the_chart_places_it_in_the_layout_and_associates(client, mock):
    dashboard = Dashboard(dashboard_title="Panel", id=5)
    dashboard._factory = client.dashboards
    chart = TableChart.from_json(chart_json(None) | {"datasource_id": 1, "datasource_type": "table"})
    mock.post(f"{API}/chart/", json={"id": 9, "result": {}})
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9)})
    mock.put(f"{API}/chart/9", json={"result": {}})

    dashboard.add_chart(chart, "Title on the dashboard")

    assert chart.id == 9
    assert dashboard.position.chart_ids() == [9]
    assert puts(mock, "/api/v1/chart/9") == [{"dashboards": [5]}]


def test_get_charts_uses_the_dashboard_route_and_tolerates_unmodeled_type(client, mock):
    mock.get(f"{API}/dashboard/5", json={"id": 5, "result": {"id": 5, "dashboard_title": "P"}})
    mock.get(f"{API}/dashboard/5/charts", json={"result": [{"id": 1, "slice_name": "a", "viz_type": "table"},
                                                           {"id": 2, "slice_name": "b", "viz_type": "histogram_v2"}]})
    mock.get(f"{API}/chart/1", json={"id": 1, "result": chart_json(1)})
    mock.get(f"{API}/chart/2", json={"id": 2, "result": chart_json(2, viz_type="histogram_v2")})

    charts = client.dashboards.get(5).get_charts()

    assert type(charts[0]).__name__ == "TableChart" and isinstance(charts[1], UnsupportedObject)


def test_delete_returns_bool_and_removes_charts_when_requested(client, mock):
    mock.get(f"{API}/dashboard/5", json={"id": 5, "result": {"id": 5, "dashboard_title": "P"}})
    mock.get(f"{API}/dashboard/5/charts", json={"result": [{"id": 1}]})
    mock.get(f"{API}/chart/1", json={"id": 1, "result": chart_json(1)})
    mock.delete(f"{API}/dashboard/5", json={"message": "OK"})
    mock.delete(f"{API}/chart/1", json={"message": "OK"})

    assert client.dashboards.get(5).delete(exclude_charts=True) is True
    assert [r.path for r in mock.request_history if r.method == "DELETE"] == ["/api/v1/dashboard/5", "/api/v1/chart/1"]


def test_get_chart_data_uses_the_saved_query_context_and_checks_the_dashboard(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[5])})
    mock.get(f"{API}/chart/9/data/", json={"result": [{"rowcount": 2, "data": [{"campus": "North", "count": 3}]}]})

    assert client.charts.get_chart_data(9, dashboard_id=5)[0]["rowcount"] == 2
    with pytest.raises(NotFound):
        client.charts.get_chart_data(9, dashboard_id=7)


def test_add_and_attach_validates_before_creating_the_chart(client, mock):
    chart = TableChart.from_json(chart_json(None) | {"datasource_id": 1, "datasource_type": "table"})

    with pytest.raises(DashboardValidationError):
        client.charts.add_and_attach_to_dashboard(chart, "Title")
    assert not any(r.method == "POST" and r.path == "/api/v1/chart/" for r in mock.request_history)


# --- Layout placement ----------------------------------------------------------------------

def test_full_row_raises_without_relocate_and_opens_new_row_with_relocate():
    pos = Metadataposition()
    tab = pos.add_tab("Tab")
    first = pos.add_markdown("a", parent=tab, width=8)
    row = first.parent

    with pytest.raises(NodePositionValidationError):
        pos.add_markdown("b", parent=row, width=8, relocate=False)

    second = pos.add_markdown("c", parent=row, width=8)
    assert second.parent is not row and second.parent.type_ == ItemPositionType.ROW


def test_item_goes_to_sibling_row_with_room():
    pos = Metadataposition()
    tab = pos.add_tab("Tab")
    full_row = pos.add_markdown("a", parent=tab, width=12).parent
    free_row = pos.add_markdown("b", parent=tab, width=4).parent

    new = pos.add_markdown("c", parent=full_row, width=4)

    assert new.parent is free_row


def test_pie_validate_accepts_chart_created_in_code_and_rejects_non_pair_orderby():
    from supersetapiplus.base.datasource import DataSource
    from supersetapiplus.charts.pie import PieChart
    from supersetapiplus.exceptions import ValidationError

    chart = PieChart.instance(slice_name="p", datasource=DataSource(id=1, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    chart.validate()

    chart.query_context.queries[0].orderby = [["count", True]]
    with pytest.raises(ValidationError, match="tuple"):
        chart.query_context.validate()


def test_markdown_item_position_is_still_available():
    assert MarkdownItemPosition(code="x").width == 4

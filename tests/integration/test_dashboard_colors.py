"""Color labels of saved charts and dashboards (client.dashboard_colors), from the chart data the real Superset
returns for the query the UI builds: the labels each plugin registers in the categorical color scale."""
from supersetapiplus.charts.types.time import TimeGrain
from supersetapiplus.dashboards.dashboards import Dashboard

from .conftest import new_chart, unique_name


def test_labels_of_saved_charts_come_from_their_data(client, dataset, cleanup, add_chart):
    pie, table = add_chart("pie"), add_chart("table")
    bars = new_chart("echarts_timeseries_bar", dataset)
    bars.set_x_axis("day")
    cleanup.chart(client.charts.add(bars))

    assert sorted(client.dashboard_colors.chart_labels(pie.id)) == ["North", "South"]
    assert sorted(client.dashboard_colors.chart_labels(bars)) == ["North", "South"]  # one series per campus
    assert client.dashboard_colors.chart_labels(table.id) is None


def test_a_chart_read_by_id_gets_the_query_explore_builds_with_the_dataset_temporal_columns(client, dataset,
                                                                                            cleanup):
    """Explore hides the time grain of a chart whose x axis is not temporal (the dataset's temporal columns say so):
    a chart read by id is queried without it, not with a time grain on a numeric x axis."""
    bars = new_chart("echarts_timeseries_bar", dataset)
    bars.set_x_axis("total")
    bars.params.time_grain_sqla = TimeGrain.DAY
    cleanup.chart(client.charts.add(bars))
    saved = client.charts.get(bars.id)

    assert sorted(client.dashboard_colors.chart_labels(saved)) == ["North", "South"]
    assert [column.get("timeGrain") for column in saved.ui_query_context()["queries"][0]["columns"]
            if isinstance(column, dict)] == [None]


def test_labels_of_a_dashboard_are_given_per_chart_that_registers_labels(client, cleanup, add_chart):
    pie, word_cloud, table = add_chart("pie"), add_chart("word_cloud"), add_chart("table")
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    cleanup.dashboard(client.dashboards.add(dashboard))
    for chart in (pie, word_cloud, table):
        client.charts.add_to_dashboard(chart, dashboard.id)

    labels = client.dashboard_colors.dashboard_labels(dashboard.id)
    assert {chart_id: sorted(chart_labels) for chart_id, chart_labels in labels.items()} == {
        pie.id: ["North", "South"], word_cloud.id: ["North", "South"]}

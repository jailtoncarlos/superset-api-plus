"""Themes against the real Superset 6.1: CRUD, the dashboard binding, and the ECharts overrides of a theme as the
dashboard page draws them (browser)."""
import os

import pytest

from supersetapiplus import Dashboard, Theme
from supersetapiplus.exceptions import ResourceNotFoundError

from .conftest import new_chart, unique_name

BAR_LABELS = {"echarts_timeseries_bar": {"series": {"label": {"show": True, "position": "inside", "color": "#ffffff"}}}}

# Records the texts ECharts draws on each chart canvas, with their color, keyed by the chart title of its holder.
RECORD_CANVAS_TEXT = """
window.__drawn = {};
const fillText = CanvasRenderingContext2D.prototype.fillText;
CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
  const holder = this.canvas && this.canvas.closest && this.canvas.closest('.dashboard-component-chart-holder');
  const title = holder && holder.querySelector('.header-title');
  if (title) (window.__drawn[title.textContent.trim()] = window.__drawn[title.textContent.trim()] || []).push([String(text), String(this.fillStyle)]);
  return fillText.call(this, text, ...rest);
};
"""


@pytest.fixture
def add_theme(client):
    created: list[int] = []

    def create(by_chart_type=None) -> Theme:
        theme = Theme(theme_name=unique_name("theme"))
        if by_chart_type:
            theme.set_echarts_overrides(by_chart_type=by_chart_type)
        created.append(client.themes.add(theme))
        return theme
    yield create
    for pk in created:
        try:
            client.themes.delete(pk)
        except ResourceNotFoundError:
            pass


def test_theme_round_trip_rename_and_delete(client, add_theme):
    theme = add_theme(BAR_LABELS)

    fetched = client.themes.get(theme.id)
    assert fetched.json_data == theme.json_data and fetched.config["token"]["echartsOptionsOverridesByChartType"]
    assert fetched.is_system is False

    fetched.theme_name = f"{theme.theme_name}-renamed"
    fetched.save()
    assert client.themes.get(theme.id).theme_name.endswith("-renamed")

    assert client.themes.delete(theme.id) is True
    with pytest.raises(ResourceNotFoundError):
        client.themes.get(theme.id)


def test_dashboard_theme_is_bound_kept_on_save_and_unbound(client, add_theme, cleanup):
    theme = add_theme()
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    dashboard.set_theme(theme)
    cleanup.dashboard(client.dashboards.add(dashboard))

    fetched = client.dashboards.get(dashboard.id)
    assert fetched.theme_id == theme.id

    fetched.dashboard_title = f"{dashboard.dashboard_title}-changed"
    fetched.save()  # a save that does not touch the theme keeps it
    assert client.dashboards.get(dashboard.id).theme_id == theme.id

    fetched.set_theme(None)
    fetched.save()
    assert client.dashboards.get(dashboard.id).theme_id is None


def drawn_texts(client, dashboard_id: int) -> dict[str, list[list[str]]]:
    from playwright.sync_api import sync_playwright

    url = client.host.rstrip("/")
    cookies = client.session.cookies.get_dict()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROME_PATH") or None)
        try:
            context = browser.new_context(viewport={"width": 1400, "height": 1000})
            context.add_cookies([{"name": name, "value": value, "url": url} for name, value in cookies.items()])
            context.add_init_script(RECORD_CANVAS_TEXT)
            page = context.new_page()
            page.goto(f"{url}/superset/dashboard/{dashboard_id}/", timeout=60000)
            page.wait_for_selector(".dashboard-component-chart-holder canvas", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(3000)  # chart animations
            return dict(page.evaluate("window.__drawn"))
        finally:
            browser.close()


def test_a_chart_type_override_of_the_theme_applies_to_that_type_on_the_bound_dashboard_only(
        client, dataset, add_theme, cleanup, chromium):
    """The bar labels of the theme (every series, inside the bar, in the color of the rule) are drawn with the
    Superset formatter (10000.37 as 10k) on the bound dashboard; a line chart of the same dashboard and the same bar chart on another dashboard
    draw no value label."""
    theme = add_theme(BAR_LABELS)
    charts = {}
    for viz_type in ("echarts_timeseries_bar", "echarts_timeseries_line"):
        chart = new_chart(viz_type, dataset, unique_name(viz_type))
        chart.params.metrics = []
        chart.add_custom_metric("value", sql_expression="SUM(total) * 1000 + 0.37")
        chart.params.groupby = []
        chart.set_x_axis("campus" if viz_type == "echarts_timeseries_bar" else "day")
        chart.query_context.form_data.metrics = chart.params.metrics
        chart.query_context.form_data.groupby = chart.params.groupby
        cleanup.chart(client.charts.add(chart))
        charts[viz_type] = chart
    themed, plain = Dashboard(dashboard_title=unique_name("themed")), Dashboard(dashboard_title=unique_name("plain"))
    themed.set_theme(theme)
    for dashboard in (themed, plain):
        cleanup.dashboard(client.dashboards.add(dashboard))
    themed.add_chart(charts["echarts_timeseries_bar"], "Bars", width=6)
    themed.add_chart(charts["echarts_timeseries_line"], "Lines", width=6)
    plain.add_chart(charts["echarts_timeseries_bar"], "Bars", width=6)
    for dashboard in (themed, plain):
        dashboard.save()

    on_themed, on_plain = drawn_texts(client, themed.id), drawn_texts(client, plain.id)

    texts = {title: {text for text, _ in drawn} for title, drawn in on_themed.items()}
    values = {"10k", "7k"}  # the y_axis_format of the chart (SMART_NUMBER), not the raw 10000.37 and 7000.37
    assert values <= texts["Bars"] and not {"10000.37", "7000.37"} & texts["Bars"], texts["Bars"]
    assert {color for text, color in on_themed["Bars"] if text in values} == {"#ffffff"}  # the color of the rule
    assert not values & texts["Lines"], texts["Lines"]
    assert not values & {text for text, _ in on_plain["Bars"]}, on_plain["Bars"]


@pytest.mark.parametrize("change_to_b", [True, False])
def test_a_fetch_reads_the_current_binding_so_the_next_save_keeps_it(client, add_theme, cleanup, change_to_b):
    """Loaded with theme A, changed on the server to theme B (or unbound), fetched and saved: the server's binding
    stays."""
    theme_a, theme_b = add_theme(), add_theme()
    dashboard = Dashboard(dashboard_title=unique_name("dash"))
    dashboard.set_theme(theme_a)
    cleanup.dashboard(client.dashboards.add(dashboard))
    loaded = client.dashboards.get(dashboard.id)
    elsewhere = client.dashboards.get(dashboard.id)
    elsewhere.set_theme(theme_b if change_to_b else None)
    elsewhere.save()

    loaded.fetch()
    loaded.dashboard_title = f"{dashboard.dashboard_title}-changed"
    loaded.save()

    assert client.dashboards.get(dashboard.id).theme_id == (theme_b.id if change_to_b else None)

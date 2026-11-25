"""Browser check of a dashboard (services.dashboard_browser): the measures against the profile's tolerances and
their matching to the layout components. Pure logic, no HTTP and no browser; the check in Chromium against the real
Superset is in tests/integration (test_dashboards.py and every example dashboard, skipped without Playwright)."""
from types import SimpleNamespace

import pytest
import requests

from supersetapiplus.dashboards.layout.sizing import ChartShape, calibrated_profile
from supersetapiplus.services.dashboard_browser import (
    BrowserComponent,
    BrowserReport,
    DashboardBrowserCheck,
    _match,
    _Placed,
    _problems,
)

PROFILE = calibrated_profile()
TABLE = _Placed("CHART-a", "Table", 1, ChartShape.TABLE)
BARS = _Placed("CHART-b", "Bars", 2, ChartShape.HORIZONTAL_BARS)
NOTE = _Placed("MARKDOWN-c", "markdown MARKDOWN-c", None, ChartShape.MARKDOWN)


def measured(**values):
    return {"chartId": None, "title": None, "scrolls": False, "empty": None, "bars": None, "clipped": False, **values}


def test_each_measure_is_checked_against_the_tolerance_of_the_profile():
    tolerated = PROFILE.max_empty + PROFILE.table.footer
    assert _problems(TABLE, measured(empty=tolerated), PROFILE, False, None) == ()
    assert _problems(TABLE, measured(empty=tolerated + 50), PROFILE, False, None) == (
        f"{tolerated + 50:.0f} px empty below the content (tolerated {tolerated:.0f})",)
    assert _problems(TABLE, measured(scrolls=True, clipped=True), PROFILE, False, None) == (
        "the content scrolls", "the title is clipped")
    assert _problems(TABLE, measured(scrolls=True), PROFILE, True, None) == ()  # scrolls by design
    thin = PROFILE.bars.min_band * PROFILE.bars.bar_share - 5
    assert _problems(BARS, measured(), PROFILE, False, 30) == ()
    assert _problems(BARS, measured(), PROFILE, False, thin)[0].startswith(f"bars {thin:.0f} px thick, outside")


def test_charts_are_matched_by_chart_id_and_markdown_in_order_when_all_are_drawn():
    drawn = [measured(chartId=2, title="Bars"), measured(), measured(chartId=1, title="Table")]
    assert _match([TABLE, BARS, NOTE], drawn) == {"CHART-a": drawn[2], "CHART-b": drawn[0], "MARKDOWN-c": drawn[1]}
    other_note = _Placed("MARKDOWN-d", "markdown MARKDOWN-d", None, ChartShape.MARKDOWN)
    # Two markdown blocks placed, one drawn (the other in a closed tab): which one is unknown, none is matched.
    assert "MARKDOWN-c" not in _match([TABLE, NOTE, other_note], drawn)


def test_the_report_lists_problems_and_what_was_not_shown():
    shown = BrowserComponent("CHART-a", "Table", 1366, True, scrolls=True, problems=("the content scrolls",))
    hidden = BrowserComponent("CHART-b", "Bars", 1366, False)
    report = BrowserReport(1, (shown, hidden))
    assert report.problems == [shown]
    assert report.summary().splitlines() == ["Table @ 1366 px: the content scrolls", "Bars @ 1366 px: not shown"]


def test_the_browser_check_needs_the_session_cookie():
    client = SimpleNamespace(session=requests.Session())
    with pytest.raises(ValueError, match="enable_session_mode"):
        DashboardBrowserCheck(client).check(1)


class FakeBrowser:
    """A stand-in for playwright.sync_api: records the cookies and the selector waited for, draws nothing."""

    def __init__(self):
        self.cookies, self.selectors, self.launched = [], [], False

    def sync_playwright(self):
        fake = self

        class Manager:
            def __enter__(self):
                return SimpleNamespace(chromium=SimpleNamespace(launch=fake.launch))

            def __exit__(self, *exc):
                return False
        return Manager()

    def launch(self, **kwargs):
        self.launched = True
        page = SimpleNamespace(goto=lambda *a, **k: None, wait_for_selector=lambda s, **k: self.selectors.append(s),
                               wait_for_load_state=lambda *a, **k: None, wait_for_timeout=lambda *a: None,
                               evaluate=lambda script, *args: [] if args else None)
        context = SimpleNamespace(add_cookies=self.cookies.extend, new_page=lambda: page, close=lambda: None)
        return SimpleNamespace(new_context=lambda **kwargs: context, close=lambda: None)


def client_with_layout(layout: dict, renew: bool = False) -> SimpleNamespace:
    """A client whose dashboard has `layout`; with `renew`, reading it renews the session (an expired cookie)."""
    from supersetapiplus.dashboards.layout import DashboardLayout

    client = SimpleNamespace(host="http://superset", session=requests.Session(),
                             charts=SimpleNamespace(get=lambda chart_id: None))
    client.session.cookies.set("session", "expired")

    def get(dashboard_id):
        if renew:
            client.session = requests.Session()
            client.session.cookies.set("session", "renewed")
        return SimpleNamespace(position_json=DashboardLayout.from_json(layout))
    client.dashboards = SimpleNamespace(get=get)
    return client


MARKDOWN_ONLY = {"ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
                 "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["MARKDOWN-a"], "parents": ["ROOT_ID"]},
                 "MARKDOWN-a": {"type": "MARKDOWN", "id": "MARKDOWN-a", "children": [], "parents": ["ROOT_ID", "GRID_ID"],
                                "meta": {"code": "## Notes", "width": 4, "height": 20}}}


@pytest.fixture
def fake_browser(monkeypatch):
    browser = FakeBrowser()
    monkeypatch.setitem(__import__("sys").modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(__import__("sys").modules, "playwright.sync_api",
                        SimpleNamespace(sync_playwright=browser.sync_playwright))
    return browser


def test_the_browser_gets_the_session_cookie_renewed_by_the_api_reads(fake_browser):
    DashboardBrowserCheck(client_with_layout(MARKDOWN_ONLY, renew=True)).check(1)
    assert {cookie["value"] for cookie in fake_browser.cookies} == {"renewed"}


def test_a_markdown_only_dashboard_is_waited_for_by_its_markdown(fake_browser):
    report = DashboardBrowserCheck(client_with_layout(MARKDOWN_ONLY)).check(1)
    assert all(".dashboard-markdown" in selector for selector in fake_browser.selectors) and fake_browser.selectors
    assert [item.shown for item in report.components] == [False] * len(PROFILE.viewports)  # the fake draws nothing


def test_a_dashboard_without_components_is_reported_empty_without_opening_a_browser(fake_browser):
    empty = {key: value for key, value in MARKDOWN_ONLY.items() if key != "MARKDOWN-a"}
    empty["GRID_ID"] = {**empty["GRID_ID"], "children": []}
    assert DashboardBrowserCheck(client_with_layout(empty)).check(1).components == ()
    assert not fake_browser.launched

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

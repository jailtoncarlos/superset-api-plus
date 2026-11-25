"""Profile logic of bin/scripts/calibrate_sizing.py on synthetic browser measures (the measuring itself needs
Playwright and the test stack, and is checked by running the script: see AGENTS.md)."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "bin" / "scripts" / "calibrate_sizing.py"
spec = importlib.util.spec_from_file_location("calibrate_sizing", SCRIPT)
calibrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibrate)

LINE = 25.1
FRAME = {"header": 33.1, "title_area": 280.0, "title_char": 7.85}
TITLE = "A chart title so long that it wraps in four or more lines on a narrow chart, more than the dashboard shows"


def header(lines: int) -> dict:
    return {**FRAME, "header": FRAME["header"] + (lines - 1) * LINE}


def test_titles_shown_whole_are_not_clamped():
    assert calibrate.title_growth(FRAME, header(3), LINE) == 2
    assert calibrate.title_max_lines(FRAME, header(4), TITLE, LINE) is None


def test_a_theme_that_clamps_titles_at_one_line_can_be_calibrated():
    assert calibrate.title_growth(FRAME, header(1), LINE) == 0  # the long title does not grow the header
    assert calibrate.title_max_lines(FRAME, header(1), TITLE, LINE) == 1
    assert calibrate.title_max_lines(FRAME, header(2), TITLE, LINE) == 2


def test_a_header_that_does_not_grow_by_whole_title_lines_is_refused():
    with pytest.raises(RuntimeError, match="not a whole number"):
        calibrate.title_growth(FRAME, {**FRAME, "header": FRAME["header"] + LINE / 2}, LINE)

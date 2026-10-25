"""The drift report of bin/scripts/superset_drift.py: what it reports, what it ignores and when it fails.

The extractors are replaced by in-memory excerpts (the script itself downloads the Superset sources, which
the scheduled workflow does); these tests check the comparison and the exit status without network.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "bin" / "scripts" / "superset_drift.py"
spec = importlib.util.spec_from_file_location("superset_drift", SCRIPT)
drift = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = drift  # dataclasses resolve annotations through the module
spec.loader.exec_module(drift)


def test_identical_excerpts_have_no_difference():
    excerpt = {"frontend": {"VizType": {"Pie": "pie"}}, "provenance": {"sha": "a"}}
    assert drift.compare(excerpt, excerpt, 3) == []


def test_provenance_and_version_stamps_are_ignored():
    pinned = {"superset_version": "6.1.0", "provenance": {"sha": "a"}, "backend": {"A": {"X": "x"}}}
    current = {"superset_version": "master", "provenance": {"sha": "b"}, "backend": {"A": {"X": "x"}}}
    assert drift.compare(pinned, current, 3) == []


def test_added_removed_and_changed_values_are_reported_by_path():
    pinned = {"frontend": {"VizType": {"Pie": "pie", "Old": "old"}}, "numbers": {"GRID": 12}}
    current = {"frontend": {"VizType": {"Pie": "pie", "New": "new"}}, "numbers": {"GRID": 24}}
    assert drift.compare(pinned, current, 3) == [
        '+ frontend.VizType.New "new"',
        '- frontend.VizType.Old "old"',
        "~ numbers.GRID 12 → 24",
    ]


def test_lists_of_values_report_the_items_that_changed():
    pinned = {"fab": {"filter_operators": ["eq", "ct"]}}
    current = {"fab": {"filter_operators": ["eq", "sw"]}}
    assert drift.compare(pinned, current, 3) == ['+ fab.filter_operators[] "sw"', '- fab.filter_operators[] "ct"']


def test_changes_below_the_depth_are_reported_as_one_line():
    pinned = {"layouts": {"births": {"position": {"CHART-1": {"meta": {"width": 4}}}}}}
    current = {"layouts": {"births": {"position": {"CHART-1": {"meta": {"width": 6}}}}}}
    [line] = drift.compare(pinned, current, 2)
    assert line.startswith("~ layouts.births ")


@pytest.fixture
def excerpts(monkeypatch, tmp_path):
    """Pinned fixtures in a temporary directory and extractors returning `by_ref[ref]` (default: the pinned)."""
    pinned = {prefix: {"provenance": {}, "values": {"A": "a"}} for prefix in drift.EXCERPTS}
    for prefix, data in pinned.items():
        (tmp_path / f"{prefix}_6.1.0.json").write_text(json.dumps(data), encoding="utf-8")
    by_ref = {}
    monkeypatch.setattr(drift, "FIXTURES", tmp_path)
    monkeypatch.setattr(drift, "resolve", lambda ref: "6.2.0" if ref == "latest" else ref)
    monkeypatch.setattr(drift, "extract", lambda script, ref, out_dir: by_ref.get(ref, {"values": {"A": "a"}}))
    return by_ref


def test_the_pinned_version_comes_from_the_enums_excerpt(excerpts):
    assert drift.pinned_version() == "6.1.0"


def test_differences_of_a_report_only_ref_do_not_fail(excerpts, capsys):
    excerpts["master"] = {"values": {"A": "b"}}
    assert drift.main(["master", "--fail-on", "latest"]) == 0
    assert "## master: differs" in capsys.readouterr().out


def test_differences_of_the_newest_release_fail(excerpts, capsys):
    excerpts["6.2.0"] = {"values": {"A": "a", "B": "b"}}
    assert drift.main(["--fail-on", "latest"]) == 1
    assert "## 6.2.0 (latest): differs" in capsys.readouterr().out


def test_an_extraction_failure_is_reported_and_fails_a_checked_ref(excerpts, monkeypatch, capsys):
    def failing(script, ref, out_dir):
        raise RuntimeError("SystemExit: Operators not found")
    monkeypatch.setattr(drift, "extract", failing)
    assert drift.main(["--fail-on", "6.1.0"]) == 1
    assert "**extraction failed**: SystemExit: Operators not found" in capsys.readouterr().out

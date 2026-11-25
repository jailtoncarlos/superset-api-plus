"""Heights estimated from the content (supersetapiplus.dashboards.layout.sizing): pure arithmetic on a synthetic
measure profile, no HTTP. The calibrated profiles and their check in a browser come with the calibration script."""
import tracemalloc

import pytest
from pydantic import ValidationError

from supersetapiplus.dashboards import layout
from supersetapiplus.dashboards.layout import sizing
from supersetapiplus.dashboards.layout.sizing import (
    BarsContent,
    ChartShape,
    Layout,
    SizingProfile,
    TableContent,
    chart_shape,
    estimate_horizontal_bars,
    estimate_markdown,
    estimate_pivot_table,
    estimate_table,
    to_units,
    width_px,
    wrap_label,
)
from supersetapiplus.exceptions import LayoutWarning, SizingWarning

PROFILE = SizingProfile.model_validate({
    "superset_version": "test", "theme": "default", "viewports": [1366, 1920],
    "grid": {"page_margin": 32, "vertical_filter_bar": 260},
    "frame": {"padding": 35, "min_header": 28, "title_line": 25.2, "title_char": 7.9, "title_controls": 30},
    "table": {"header": 49, "narrow_header": 87, "row": 29.4, "text_line": 18.9, "footer": 28, "search": 41,
              "pagination": 58, "label_chars": 85, "unfixed_label_chars": 26, "min_label_lines": 1},
    "pivot_table": {"header": 95, "row": 26.8, "text_line": 17.8, "footer": 36, "label_chars": 72},
    "bars": {"band": 44, "min_band": 26, "max_band": 40, "axes_and_legend": 85, "axes_without_legend": 61,
             "label_chars": 85, "label_line": 12, "label_padding": 8},
    "markdown": {"padding": 16, "char_width_em": 0.51, "wrap_slack_chars": 4, "rule_height": 3, "rule_margin": 7,
                 "list_margin": 14, "list_indent": 40,
                 "styles": {"p": {"font": 14, "line": 22, "margin_top": 0, "margin_bottom": 8},
                            "li": {"font": 14, "line": 22, "margin_top": 0, "margin_bottom": 0},
                            "h1": {"font": 30, "line": 42, "margin_top": 12, "margin_bottom": 12},
                            "h2": {"font": 24, "line": 33.6, "margin_top": 12, "margin_bottom": 8},
                            "h3": {"font": 19, "line": 26.6, "margin_top": 12, "margin_bottom": 4}}},
    "max_empty": 96, "max_empty_pivot_table": 280,
})


def test_grid_constants_match_the_layout_package():
    assert (sizing.GRID_MIN_ROW_UNITS, sizing.GRID_MAX_ROW_UNITS, sizing.GRID_COLUMN_COUNT) == \
        (layout.GRID_MIN_ROW_UNITS, layout.GRID_MAX_ROW_UNITS, layout.GRID_COLUMN_COUNT)


def test_units_round_up_within_the_grid_bounds():
    assert (to_units(8), to_units(64), to_units(65), to_units(10_000)) == (5, 8, 9, 100)


def test_component_width_on_a_viewport():
    # 1366 - 32 page margins - 260 vertical filter bar = 1074 px of grid; 12 columns take it all.
    assert width_px(12, 1366, PROFILE) == pytest.approx(1074)
    assert width_px(12, 1366, PROFILE, vertical_filter_bar=False) == pytest.approx(1334)
    assert width_px(6, 1366, PROFILE) == pytest.approx((1074 - 176) / 12 * 6 + 5 * 16)


def test_labels_wrap_between_words():
    assert wrap_label("one two three four", 9) == ["one two", "three", "four"]
    assert wrap_label("averyveryverylongword x", 5) == ["averyveryverylongword", "x"]
    assert wrap_label("", 10) == [""]


def test_chart_shapes():
    assert chart_shape({"viz_type": "table"}) is ChartShape.TABLE
    assert chart_shape({"viz_type": "pivot_table_v2"}) is ChartShape.PIVOT_TABLE
    assert chart_shape({"viz_type": "echarts_timeseries_bar", "orientation": "horizontal"}) is ChartShape.HORIZONTAL_BARS
    assert chart_shape({"viz_type": "echarts_timeseries_bar", "orientation": "vertical"}) is None


def test_table_height_by_hand():
    estimate = estimate_table(TableContent(rows=3), PROFILE)
    # 1366 px: frame 35 + 28 (one-line header), table header 49, 3 rows of 29.4, footer 28 = 228.2 px -> 29 units;
    # 1920 px needs the same plus 96 px of tolerated empty space = 324.2 px -> 41 units.
    assert (estimate.min_units, estimate.recommended_units, estimate.max_units) == (29, 29, 41)
    assert estimate.reasons == () and not estimate.approximate
    assert estimate.problem(29) is None and "below" in estimate.problem(28) and "empty" in estimate.problem(42)


def test_table_rows_grow_with_their_wrapped_labels_and_search_and_pagination_add_up():
    long_label = " ".join(["word"] * 40)  # 199 characters: 3 lines of 85
    plain = estimate_table(TableContent(rows=2, fixed_label_width=True), PROFILE).min_units
    wrapped = estimate_table(TableContent(rows=2, labels=[long_label], fixed_label_width=True), PROFILE).min_units
    assert to_units((wrapped - plain) * 8) >= to_units(2 * 18.9) - 1
    full = estimate_table(TableContent(rows=2, search=True, pagination=True), PROFILE).min_units
    assert full == to_units(35 + 28 + 49 + 2 * 29.4 + 28 + 41 + 58)


def test_table_rows_are_capped_and_unknown_rows_use_the_cap():
    capped = estimate_table(TableContent(rows=40), PROFILE, max_rows=15)
    assert capped.min_units == estimate_table(TableContent(rows=15), PROFILE).min_units
    assert any("scrolls" in reason for reason in capped.reasons)
    unknown = estimate_table(TableContent(rows=None), PROFILE, max_rows=15)
    assert unknown.min_units == capped.min_units and any("unknown" in reason for reason in unknown.reasons)


@pytest.mark.parametrize("estimate", [estimate_table, estimate_pivot_table])
@pytest.mark.parametrize("labels", [(), ("word " * 40,)])
def test_capped_table_memory_is_bounded_for_large_row_counts(estimate, labels):
    tracemalloc.start()
    try:
        estimate(TableContent(rows=1_000_000, labels=labels), PROFILE, max_rows=15)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # A million row pointers take several MB; sizing 15 visible rows should stay well below 1 MB.
    assert peak < 1_000_000


@pytest.mark.parametrize("estimate, expected_units", [(estimate_table, 32), (estimate_pivot_table, 38)])
def test_capped_tables_keep_the_tallest_labels_beyond_the_cap(estimate, expected_units):
    labels = ["short"] * 15 + ["word " * 20, "word " * 40]
    result = estimate(TableContent(rows=20, labels=labels, fixed_label_width=True), PROFILE, max_rows=2)
    # The last two labels wrap to two and three lines: 255.5 px for a table, 301 px for a pivot table.
    assert (result.min_units, result.recommended_units) == (expected_units, expected_units)


def test_a_narrower_table_has_a_taller_header_and_a_long_title_wraps():
    assert estimate_table(TableContent(rows=3), PROFILE, Layout(columns=6)).min_units > \
        estimate_table(TableContent(rows=3), PROFILE).min_units
    title = "A title " * 30
    assert estimate_table(TableContent(rows=3, title=title), PROFILE).min_units > \
        estimate_table(TableContent(rows=3), PROFILE).min_units


def test_pivot_table_estimates_are_approximate():
    estimate = estimate_pivot_table(TableContent(rows=4), PROFILE)
    assert estimate.approximate and estimate.min_units == to_units(35 + 28 + 95 + 4 * 26.8 + 36)


def test_horizontal_bars_range_and_band_growing_with_long_labels():
    estimate = estimate_horizontal_bars(BarsContent(bars=10), PROFILE)
    assert estimate.recommended_units == to_units(35 + 28 + 10 * 44 + 85)
    assert estimate.min_units == to_units(35 + 28 + 10 * 26 + 85) <= estimate.recommended_units <= estimate.max_units
    long_labels = [" ".join(["word"] * 60)]  # 4 lines of 85 characters: 4 * 12 + 8 = 56 px per bar
    wide = estimate_horizontal_bars(BarsContent(bars=10, labels=long_labels, legend=False), PROFILE)
    assert wide.recommended_units == to_units(35 + 28 + 10 * 56 + 61) and wide.reasons


def test_markdown_height_and_html_left_unestimated():
    estimate = estimate_markdown("# Title\n\nA short paragraph.", PROFILE)
    # 16 padding + h1 (12 top + 42) + p (max(12, 0) + 22) + 8 bottom + 16 padding = 128 px -> 16, +1 margin unit.
    assert (estimate.min_units, estimate.recommended_units) == (16, 17)
    html = estimate_markdown("<table><tr><td>x</td></tr></table>", PROFILE)
    assert html.approximate and html.reasons


@pytest.mark.parametrize("line_break", ["<br>", "<br/>", "<br />", "<BR>", "<Br />", "  \n"])
def test_markdown_explicit_breaks_preserve_rendered_lines(line_break):
    estimate = estimate_markdown(line_break.join(["one", "two", "three"]), PROFILE)
    # 32 px padding + three 22 px lines + 8 px bottom margin = 106 px -> 14 units, plus one margin unit.
    assert (estimate.min_units, estimate.recommended_units, estimate.max_units) == (14, 15, 26)
    assert estimate.reasons == () and not estimate.approximate


def test_profiles_reject_invalid_measures():
    with pytest.raises(ValidationError):
        SizingProfile.model_validate({**PROFILE.model_dump(), "viewports": []})
    with pytest.raises(ValidationError):
        SizingProfile.model_validate({**PROFILE.model_dump(), "max_empty": -1})


def test_sizing_warning_is_not_a_layout_warning():
    assert issubclass(SizingWarning, UserWarning) and not issubclass(SizingWarning, LayoutWarning)


def test_list_margins_apply_only_at_the_list_boundaries():
    # 16 + 16 padding, 14 px list margin above and below, three items of 22 px with no margin between them.
    assert sizing.markdown_px("- a\n- b\n- c", 12, 1366, PROFILE) == pytest.approx(32 + 14 + 3 * 22 + 14)
    # Leaving the list: the next paragraph starts after the list margin.
    assert sizing.markdown_px("- a\n\nText", 12, 1366, PROFILE) == pytest.approx(32 + 14 + 22 + 14 + 22 + 8)


def test_markdown_images_are_left_unestimated_like_html_images():
    estimate = estimate_markdown("A chart:\n\n![plot](https://example.com/plot.png)", PROFILE)
    assert estimate.approximate and any("image" in reason for reason in estimate.reasons)
    assert not estimate_markdown("A [link](https://example.com)", PROFILE).approximate


def test_soft_breaks_keep_a_space_in_a_paragraph_with_a_hard_break():
    assert [block.text for block in sizing._markdown_blocks("one\ntwo  \nthree")] == ["one two\nthree"]
    assert [block.text for block in sizing._markdown_blocks("one<br>two<br>three")] == ["one\ntwo\nthree"]


def test_bold_text_counts_in_headings_as_in_paragraphs():
    heading = "# **" + " ".join(["bold"] * 40) + "**"
    assert sizing._markdown_blocks(heading)[0].bold == len(" ".join(["bold"] * 40))
    wide_bold = PROFILE.model_copy(update={"markdown": PROFILE.markdown.model_copy(update={"bold_width": 2.0})})
    assert sizing.markdown_px(heading, 12, 1366, wide_bold) > sizing.markdown_px(heading, 12, 1366, PROFILE)


def test_bold_text_is_counted_on_its_own_hard_broken_line():
    # 12 columns on 1366 px: 141 characters per paragraph line. The first line fills one line with plain text; the
    # second has 10 bold characters. Charging the bold to the first line would wrap it to a second line.
    markdown = "x" * 141 + "  \n**" + "y" * 10 + "**"
    wide_bold = PROFILE.model_copy(update={"markdown": PROFILE.markdown.model_copy(update={"bold_width": 2.0})})
    assert sizing.markdown_px(markdown, 12, 1366, wide_bold) == sizing.markdown_px(markdown, 12, 1366, PROFILE)

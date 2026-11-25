"""Heights of dashboard components estimated from their content (no HTTP).

A chart in a dashboard has a fixed height (``meta.height`` in ``position_json``, in grid units of
``GRID_BASE_UNIT`` px). With a fixed height, a table with few rows leaves empty space below it, one with many rows
scrolls, and horizontal bars share the same height among more or fewer bars (thin bars and squeezed labels with
many, thick bars with few). This module estimates the height from the content:

- table (``table``) and pivot table (``pivot_table_v2``): chart frame (padding and the title, which wraps at the
  chart width) + header + min(rows, ``max_rows``) rows (a row grows with the lines of its wrapped label) + footer,
  search box and pagination;
- horizontal bars (``echarts_timeseries_bar`` with ``orientation: horizontal``): frame + bars × band + axes and
  legend; the band grows only when the longest label needs more lines than fit in it;
- markdown: the blocks of the text (paragraphs, headings, lists, horizontal rules) at the component width.

The measures (px of each part) depend on the Superset version, its theme and fonts, and the screen width: they come
in a :class:`SizingProfile`, calibrated in a browser (see ``docs/superset-version-bump.md``) or given by the user.
An estimate is a range: ``min_units`` is the height below which the content is cut or scrolls on the narrowest
viewport of the profile, ``max_units`` the height above which more than the profile's tolerated empty space is
left on the widest one, and ``recommended_units`` the height to use.
"""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from supersetapiplus.core.enums import StringEnum

# Grid of the dashboard renderer (superset-frontend/src/dashboard/util/constants.ts); GRID_MIN_ROW_UNITS and
# GRID_MAX_ROW_UNITS are the same as in supersetapiplus.dashboards.layout (checked by a unit test: that package
# imports this module, so it cannot be imported here).
GRID_BASE_UNIT = 8
GRID_GUTTER_SIZE = 16
GRID_COLUMN_COUNT = 12
GRID_MIN_ROW_UNITS = 5
GRID_MAX_ROW_UNITS = 100


class ChartShape(StringEnum):
    """What the sizing formulas know how to measure (a classification of this library, not a Superset value)."""
    TABLE = "table"
    PIVOT_TABLE = "pivot_table"
    HORIZONTAL_BARS = "horizontal_bars"
    MARKDOWN = "markdown"


def chart_shape(params: dict[str, object]) -> ChartShape | None:
    """The shape of a chart from its params (``viz_type`` and, for bars, ``orientation``); None when not sized."""
    viz_type = params.get("viz_type")
    if viz_type == "table":
        return ChartShape.TABLE
    if viz_type == "pivot_table_v2":
        return ChartShape.PIVOT_TABLE
    if viz_type == "echarts_timeseries_bar" and params.get("orientation") == "horizontal":
        return ChartShape.HORIZONTAL_BARS
    return None


# ------------------------------------------------------------------------------------------------ measure profile

class _Measures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GridMeasures(_Measures):
    """Width available to the grid: the viewport minus the page margins and, when open beside it, the vertical
    native filter bar."""
    page_margin: float = Field(ge=0)
    vertical_filter_bar: float = Field(ge=0)


class FrameMeasures(_Measures):
    """What a chart takes besides its content: padding, and the header with the title wrapped at the chart width."""
    padding: float = Field(ge=0)
    min_header: float = Field(ge=0)
    title_line: float = Field(gt=0)
    title_char: float = Field(gt=0)
    title_controls: float = Field(ge=0)


class TableMeasures(_Measures):
    """Table (``table``): a row is ``row`` px with one line of text and grows by ``text_line`` per extra line of its
    label. ``label_chars`` is the characters per line of the label column when its width is fixed (``columnWidth``),
    ``unfixed_label_chars`` when Superset chooses it (narrowest viewport)."""
    header: float = Field(ge=0)
    narrow_header: float = Field(ge=0)
    row: float = Field(gt=0)
    text_line: float = Field(ge=0)
    footer: float = Field(ge=0)
    search: float = Field(ge=0)
    pagination: float = Field(ge=0)
    label_chars: float = Field(gt=0)
    unfixed_label_chars: float = Field(gt=0)
    min_label_lines: int = Field(default=1, ge=1)


class PivotTableMeasures(_Measures):
    """Pivot table (``pivot_table_v2``). Its label column width cannot be fixed in Superset 6.1, so estimates are
    approximate (see :attr:`SizingEstimate.approximate`)."""
    header: float = Field(ge=0)
    row: float = Field(gt=0)
    text_line: float = Field(ge=0)
    footer: float = Field(ge=0)
    label_chars: float = Field(gt=0)


class BarMeasures(_Measures):
    """Horizontal bars: ``band`` px per bar (the category band), more when the longest label needs more lines
    (``label_line`` px each, plus ``label_padding``); ``min_band``/``max_band`` bound the thickness that reads well."""
    band: float = Field(gt=0)
    min_band: float = Field(gt=0)
    max_band: float = Field(gt=0)
    axes_and_legend: float = Field(ge=0)
    axes_without_legend: float = Field(ge=0)
    label_chars: float = Field(gt=0)
    label_line: float = Field(gt=0)
    label_padding: float = Field(ge=0)


class TextStyle(_Measures):
    """A markdown block as the theme draws it: font size, line height and margins, in px."""
    font: float = Field(gt=0)
    line: float = Field(gt=0)
    margin_top: float = Field(ge=0)
    margin_bottom: float = Field(ge=0)


class MarkdownMeasures(_Measures):
    """Markdown component: padding on each side, average character width (in em of the font), characters lost per
    line to word wrapping, block styles (``p``, ``li``, ``h1``..``h6``), horizontal rule and lists. ``bold_width``
    and ``bold_extra_line`` account for a theme or CSS that enlarges bold text (1 and 0 in the default theme)."""
    padding: float = Field(ge=0)
    char_width_em: float = Field(gt=0)
    wrap_slack_chars: float = Field(ge=0)
    styles: dict[str, TextStyle]
    rule_height: float = Field(ge=0)
    rule_margin: float = Field(ge=0)
    list_margin: float = Field(ge=0)
    list_indent: float = Field(ge=0)
    bold_width: float = Field(default=1.0, gt=0)
    bold_extra_line: float = Field(default=0.0, ge=0)


class SizingProfile(_Measures):
    """The measures of one Superset version, theme and set of viewports (screen widths in px), with the empty space
    tolerated below the content (``max_empty``) and a margin added to markdown heights (``markdown_margin_units``).
    """
    superset_version: str  # free text: the version the profile was calibrated on, e.g. "6.1.0"
    theme: str  # free text: "default", or the name of the instance's theme or CSS the profile was calibrated with
    viewports: tuple[int, ...] = Field(min_length=1)
    grid: GridMeasures
    frame: FrameMeasures
    table: TableMeasures
    pivot_table: PivotTableMeasures
    bars: BarMeasures
    markdown: MarkdownMeasures
    max_empty: float = Field(ge=0)
    max_empty_pivot_table: float = Field(ge=0)
    markdown_margin_units: int = Field(default=1, ge=0)

    @property
    def narrowest(self) -> int:
        return min(self.viewports)

    @property
    def widest(self) -> int:
        return max(self.viewports)


# ------------------------------------------------------------------------------------------------------ estimates

@dataclass(frozen=True)
class SizingEstimate:
    """Heights in grid units: below ``min_units`` the content is cut, scrolls or the bars are squeezed on the
    narrowest viewport; above ``max_units`` more than the tolerated empty space is left on the widest one.
    ``reasons`` explains each bound; ``approximate`` marks estimates the profile cannot make exact (pivot tables)."""
    min_units: int
    recommended_units: int
    max_units: int
    reasons: tuple[str, ...] = field(default=())
    approximate: bool = False

    def problem(self, height: int) -> str | None:
        """Why `height` is outside the range, or None."""
        if height < self.min_units:
            return f"height {height} is below the content's minimum of {self.min_units} units"
        if height > self.max_units:
            return f"height {height} leaves more empty space than tolerated (maximum {self.max_units} units)"
        return None


def to_units(px: float) -> int:
    """Height in grid units (rounded up), within the editor's minimum and maximum."""
    return min(GRID_MAX_ROW_UNITS, max(GRID_MIN_ROW_UNITS, math.ceil(px / GRID_BASE_UNIT - 1e-9)))


def width_px(columns: int, viewport: int, profile: SizingProfile, vertical_filter_bar: bool = True) -> float:
    """Width, in px, of a component `columns` grid columns wide on a `viewport` px screen."""
    grid = viewport - profile.grid.page_margin - (profile.grid.vertical_filter_bar if vertical_filter_bar else 0)
    column = (grid - (GRID_COLUMN_COUNT - 1) * GRID_GUTTER_SIZE) / GRID_COLUMN_COUNT
    return columns * column + (columns - 1) * GRID_GUTTER_SIZE


def wrap_label(text: str, chars: int) -> list[str]:
    """Lines of `text` wrapped at word boundaries in lines of up to `chars` characters (a word longer than a line
    stays whole). The rule a consumer can also apply in its query, so the chart shows the same lines."""
    text = " ".join(str(text or "").split())
    if not text:
        return [""]
    lines = re.sub(rf"(.{{1,{max(1, int(chars))}}})(\s+|$)", "\\1\n", text).rstrip("\n").split("\n")
    return [line for line in lines if line] or [text]


def label_lines(text: str, chars: float) -> int:
    """Lines of text the label takes in a column of `chars` characters per line."""
    return len(wrap_label(text, max(1, int(chars))))


def frame_px(title: str, columns: int, viewport: int, profile: SizingProfile, vertical_filter_bar: bool = True) -> float:
    """Px a chart takes besides its content: padding and the header, whose title wraps at the chart width."""
    frame = profile.frame
    usable = width_px(columns, viewport, profile, vertical_filter_bar) - frame.title_controls
    lines = label_lines(title, usable / frame.title_char)
    return frame.padding + max(frame.min_header, lines * frame.title_line)


@dataclass(frozen=True)
class Layout:
    """Where the component is: its width in grid columns and whether the dashboard's native filter bar is vertical
    (Superset's default, which narrows the grid while open)."""
    columns: int = GRID_COLUMN_COUNT
    vertical_filter_bar: bool = True


FULL_WIDTH = Layout()


@dataclass(frozen=True)
class TableContent:
    """A table's content: data rows (None when unknown: sized for `max_rows`), the label of each row when known,
    the chart title, whether the label column has a fixed width, and the search box and pagination."""
    rows: int | None
    labels: Sequence[str] = ()
    title: str = ""
    fixed_label_width: bool = False
    search: bool = False
    pagination: bool = False


def _row_heights(rows: int, labels: Sequence[str], row: float, text_line: float, chars: float, max_rows: int,
                 min_lines: int = 1) -> list[float]:
    """Px of each visible row: rows with a known label grow with its wrapped lines (at least `min_lines`); the
    others take one line. Above `max_rows` the tallest `max_rows` remain (the table stops growing and scrolls)."""
    heights = [row + text_line * (max(min_lines, label_lines(label, chars)) - 1) for label in labels[:rows]]
    heights += [row] * max(0, min(rows, max_rows) - len(heights))
    return sorted(heights, reverse=True)[:max_rows]


def _visible_rows(rows: int | None, max_rows: int | None, reasons: list[str]) -> tuple[int, int]:
    """(rows to measure, cap) with the reason when the content is unknown or above the cap."""
    cap = max_rows if max_rows is not None else GRID_MAX_ROW_UNITS
    if rows is None:
        reasons.append(f"row count unknown: sized for {cap} rows" if max_rows is not None
                       else "row count unknown and no max_rows: sized for one row")
        return (cap if max_rows is not None else 1), cap
    if rows > cap:
        reasons.append(f"{rows} rows above the maximum of {cap}: the table scrolls")
    return max(0, rows), cap


def _range(needed: dict[int, float], profile: SizingProfile, max_empty: float, reasons: list[str],
           margin_units: int = 0, approximate: bool = False) -> SizingEstimate:
    """Estimate from the px the content needs on each viewport."""
    low = to_units(needed[profile.narrowest])
    high = to_units(needed[profile.widest] + max_empty)
    recommended = min(GRID_MAX_ROW_UNITS, low + margin_units)
    if low >= GRID_MAX_ROW_UNITS:
        reasons.append(f"the content needs more than the grid maximum of {GRID_MAX_ROW_UNITS} units")
    if high < low:
        reasons.append(f"no height avoids both cutting on {profile.narrowest} px and empty space on "
                       f"{profile.widest} px: the minimum wins")
        high = low
    return SizingEstimate(min_units=low, recommended_units=max(low, min(recommended, high)), max_units=high,
                          reasons=tuple(reasons), approximate=approximate)


def estimate_table(content: TableContent, profile: SizingProfile, layout: Layout = FULL_WIDTH,
                   max_rows: int | None = None) -> SizingEstimate:
    """Height of a table (``table``): frame + header + rows + footer (+ search and pagination)."""
    reasons: list[str] = []
    rows, cap = _visible_rows(content.rows, max_rows, reasons)
    table = profile.table
    chars, min_lines = ((table.label_chars, table.min_label_lines) if content.fixed_label_width
                        else (table.unfixed_label_chars, 1))
    body = sum(_row_heights(rows, content.labels, table.row, table.text_line, chars, cap, min_lines))
    header = table.header if layout.columns >= GRID_COLUMN_COUNT else table.narrow_header
    extras = table.footer + (table.search if content.search else 0) + (table.pagination if content.pagination else 0)
    needed = {viewport: frame_px(content.title, layout.columns, viewport, profile, layout.vertical_filter_bar)
              + header + body + extras for viewport in profile.viewports}
    return _range(needed, profile, profile.max_empty, reasons)


def estimate_pivot_table(content: TableContent, profile: SizingProfile, layout: Layout = FULL_WIDTH,
                         max_rows: int | None = None) -> SizingEstimate:
    """Height of a pivot table (``pivot_table_v2``); approximate, since its label column width is not fixed."""
    reasons: list[str] = []
    rows, cap = _visible_rows(content.rows, max_rows, reasons)
    pivot = profile.pivot_table
    body = sum(_row_heights(rows, content.labels, pivot.row, pivot.text_line, pivot.label_chars, cap))
    needed = {viewport: frame_px(content.title, layout.columns, viewport, profile, layout.vertical_filter_bar)
              + pivot.header + body + pivot.footer for viewport in profile.viewports}
    reasons.append("pivot table: the label column width is not fixed, so the estimate is approximate")
    return _range(needed, profile, profile.max_empty_pivot_table, reasons, approximate=True)


@dataclass(frozen=True)
class BarsContent:
    """Horizontal bars: number of bars (None when unknown: sized for `max_rows`), their labels when known, the
    chart title and whether the legend is shown."""
    bars: int | None
    labels: Sequence[str] = ()
    title: str = ""
    legend: bool = True


def band_px(labels: Sequence[str], profile: SizingProfile) -> float:
    """Px of each bar's band: the profile's, or more when the longest label wraps in more lines than fit in it."""
    bars = profile.bars
    lines = max([label_lines(label, bars.label_chars) for label in labels] or [1])
    return max(bars.band, lines * bars.label_line + bars.label_padding)


def estimate_horizontal_bars(content: BarsContent, profile: SizingProfile, layout: Layout = FULL_WIDTH,
                             max_rows: int | None = None) -> SizingEstimate:
    """Height of horizontal bars: frame + bars × band + axes (and legend). The range is the band thickness that
    reads well (``min_band`` to ``max_band``); the recommended height uses the profile's band."""
    reasons: list[str] = []
    count, cap = _visible_rows(content.bars, max_rows, reasons)
    count = max(1, min(count, cap))
    bars = profile.bars
    axes = bars.axes_and_legend if content.legend else bars.axes_without_legend
    band = band_px(content.labels, profile)
    if band > bars.band:
        reasons.append(f"labels wrap in more lines than fit in a {bars.band:g} px band: {band:g} px per bar")

    def height(viewport: int, per_bar: float) -> float:
        return frame_px(content.title, layout.columns, viewport, profile, layout.vertical_filter_bar) + \
            count * per_bar + axes

    low = to_units(height(profile.narrowest, max(bars.min_band, band if band > bars.band else bars.min_band)))
    recommended = to_units(height(profile.narrowest, band))
    high = max(recommended, to_units(height(profile.widest, max(bars.max_band, band))))
    return SizingEstimate(min_units=min(low, recommended), recommended_units=recommended, max_units=high,
                          reasons=tuple(reasons))


# ------------------------------------------------------------------------------------------------------- markdown

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_RULE = re.compile(r"^\s*([-_*])(\s*\1){2,}\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_HTML_BREAK = re.compile(r"<br\s*/?>", re.I)
_HTML_TAG = re.compile(r"<[^>]+>")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)")
_BOLD = re.compile(r"(\*\*|__)(.+?)\1")


def _visible_text(text: str) -> str:
    return _EMPHASIS.sub("", _HTML_TAG.sub("", _LINK.sub(r"\1", text))).strip()


def _bold_chars(text: str) -> int:
    return sum(len(_visible_text(match.group(2))) for match in _BOLD.finditer(text))


@dataclass
class _Block:
    kind: str  # "p", "li", "h1".."h6" or "hr"
    text: str = ""
    bold: int = 0


def _markdown_blocks(markdown: str) -> list[_Block]:
    """Blocks of the markdown in order; consecutive lines form a paragraph (two trailing spaces break the line)."""
    blocks: list[_Block] = []
    paragraph: list[str] = []
    bold = 0

    def close() -> None:
        nonlocal bold
        if paragraph:
            hard_break = any(part.endswith("\n") for part in paragraph)
            text = "".join(paragraph).rstrip("\n") if hard_break else " ".join(part.strip() for part in paragraph)
            blocks.append(_Block("p", text, bold))
            paragraph.clear()
            bold = 0

    for line in _HTML_BREAK.sub("  \n", markdown or "").replace("\r", "").split("\n"):
        heading, item = _HEADING.match(line.strip()), _LIST_ITEM.match(line)
        if not line.strip() or _RULE.match(line) or heading or item:
            close()
        if _RULE.match(line):
            blocks.append(_Block("hr"))
        elif heading:
            blocks.append(_Block(f"h{len(heading.group(1))}", _visible_text(heading.group(2))))
        elif item:
            blocks.append(_Block("li", _visible_text(item.group(1)), _bold_chars(item.group(1))))
        elif line.strip() and (visible := _visible_text(line)):
            bold += _bold_chars(line)
            paragraph.append(visible + ("\n" if line.endswith("  ") else ""))
    close()
    return blocks


def _text_lines(block: _Block, style: TextStyle, width: float, markdown: MarkdownMeasures) -> tuple[int, int]:
    """(lines the block's text takes in `width` px, lines with bold text); each newline starts a line."""
    char = markdown.char_width_em * style.font
    per_line = max(1, int((width - markdown.wrap_slack_chars * char) // char))
    total = with_bold = 0
    remaining = block.bold
    for part in block.text.split("\n"):
        bold = min(remaining, len(part))
        remaining -= bold
        total += max(1, math.ceil((len(part) - bold + markdown.bold_width * bold) / per_line))
        with_bold += math.ceil(markdown.bold_width * bold / per_line) if markdown.bold_extra_line else 0
    return total, with_bold


def markdown_px(markdown: str, columns: int, viewport: int, profile: SizingProfile,
                vertical_filter_bar: bool = True) -> float:
    """Px a markdown component takes, with its padding (adjacent vertical margins collapse)."""
    measures = profile.markdown
    usable = width_px(columns, viewport, profile, vertical_filter_bar) - 2 * measures.padding
    total = pending_margin = 0.0
    previous: str | None = None
    for block in _markdown_blocks(markdown):
        if block.kind == "hr":
            height, top, bottom = measures.rule_height, measures.rule_margin, measures.rule_margin
        else:
            style = measures.styles[block.kind]
            width = usable - (measures.list_indent if block.kind == "li" else 0)
            lines, with_bold = _text_lines(block, style, width, measures)
            height, top, bottom = style.line * lines + measures.bold_extra_line * with_bold, style.margin_top, \
                style.margin_bottom
        if block.kind == "li" and previous != "li":
            top = max(top, measures.list_margin)
        total += max(pending_margin, top) + height
        pending_margin = measures.list_margin if block.kind == "li" else bottom
        previous = block.kind
    return 2 * measures.padding + total + pending_margin


def estimate_markdown(markdown: str, profile: SizingProfile, layout: Layout = FULL_WIDTH) -> SizingEstimate:
    """Height of a markdown component; text with HTML other than ``<br>`` (tables, images) is not measurable and
    gets the grid minimum with a reason."""
    reasons: list[str] = []
    if _HTML_TAG.search(_HTML_BREAK.sub("", markdown or "")):
        reasons.append("markdown with HTML other than <br>: not estimated")
        return SizingEstimate(GRID_MIN_ROW_UNITS, GRID_MIN_ROW_UNITS, GRID_MAX_ROW_UNITS, tuple(reasons), True)
    needed = {viewport: markdown_px(markdown, layout.columns, viewport, profile, layout.vertical_filter_bar)
              for viewport in profile.viewports}
    return _range(needed, profile, profile.max_empty, reasons, margin_units=profile.markdown_margin_units)

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

import functools
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import resources

from markdown_it import MarkdownIt
from markdown_it.token import Token
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


class SizingMode(StringEnum):
    """What the layout does, when sent, with a component whose height does not fit its content (a library choice,
    not a Superset value): nothing, a :class:`~supersetapiplus.exceptions.SizingWarning`, or a
    :class:`~supersetapiplus.exceptions.SizingError` (approximate estimates, e.g. pivot tables, only warn)."""
    OFF = "off"
    WARN = "warn"
    STRICT = "strict"


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
    label. ``label_chars`` is the characters per line of the label column when its width is fixed (``columnWidth``)
    at ``label_column_width`` px (None in a profile that does not record it), ``unfixed_label_chars`` when Superset
    chooses it (narrowest viewport)."""
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
    label_column_width: float | None = Field(default=None, gt=0)


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


#: The largest bound of a regular expression repetition in PostgreSQL (``{m,n}`` with n above it is an error).
POSTGRESQL_REPETITION_LIMIT = 255


def _line_pattern(chars: int) -> str:
    """``.{1,chars}`` for PostgreSQL: one bounded run of up to 255 characters, then optional runs of the rest."""
    chars = max(1, chars)
    runs = [f".{{1,{min(chars, POSTGRESQL_REPETITION_LIMIT)}}}"]
    rest = chars - POSTGRESQL_REPETITION_LIMIT
    while rest > 0:
        runs.append(f".{{0,{min(rest, POSTGRESQL_REPETITION_LIMIT)}}}")
        rest -= POSTGRESQL_REPETITION_LIMIT
    return "".join(runs)


def wrap_label_sql(expression: str, chars: int, dialect: str = "postgresql") -> str:
    """SQL expression of the label `expression` wrapped as :func:`wrap_label` wraps it, for the query of a chart that
    shows wrapped labels (e.g. horizontal bars sized with ``BarsContent``): whitespace collapsed, lines of up to
    `chars` characters split at word boundaries (a longer word stays whole), joined by a newline.

    Each line starts with two spaces: Superset 6.1 reserves a few px less than the longest label for the bar axis
    labels and clips the first letter. Written for Superset 6.1, which rewrites a chart's SQL (sqlglot): the newline
    is ``chr(10)`` (an ``E'...'`` string loses the backreference) and the pattern uses ``[[:space:]]``, no backslash
    before a letter. Only PostgreSQL is supported. PostgreSQL bounds a regular expression repetition at 255, so a
    wider line is matched as one bounded run of up to 255 characters followed by optional runs of the rest.
    """
    if dialect != "postgresql":
        raise ValueError(f"wrap_label_sql supports the postgresql dialect, not {dialect!r}")
    collapsed = f"btrim(regexp_replace({expression}, '[[:space:]]+', ' ', 'g'))"
    wrapped = f"rtrim(regexp_replace({collapsed}, '({_line_pattern(int(chars))})( +|$)', '\\1' || chr(10), 'g'), chr(10))"
    return f"replace('  ' || {wrapped}, chr(10), chr(10) || '  ')"


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


def _visible_rows(rows: int | None, max_rows: int | None, reasons: list[str],
                  above_cap: str = "the table scrolls") -> tuple[int, int]:
    """(rows to measure, cap) with the reason when the content is unknown or above the cap (`above_cap` says what
    happens then)."""
    cap = max_rows if max_rows is not None else GRID_MAX_ROW_UNITS
    if rows is None:
        reasons.append(f"row count unknown: sized for {cap} rows" if max_rows is not None
                       else "row count unknown and no max_rows: sized for one row")
        return (cap if max_rows is not None else 1), cap
    if rows > cap:
        reasons.append(f"{rows} rows above the maximum of {cap}: {above_cap}")
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


def label_band_px(labels: Sequence[str], profile: SizingProfile) -> float:
    """Px a bar's band needs for the longest label, wrapped in lines (never squeezed)."""
    bars = profile.bars
    lines = max([label_lines(label, bars.label_chars) for label in labels] or [1])
    return lines * bars.label_line + bars.label_padding


def band_px(labels: Sequence[str], profile: SizingProfile) -> float:
    """Px of each bar's band: the profile's, or more when the longest label wraps in more lines than fit in it."""
    return max(profile.bars.band, label_band_px(labels, profile))


def estimate_horizontal_bars(content: BarsContent, profile: SizingProfile, layout: Layout = FULL_WIDTH,
                             max_rows: int | None = None) -> SizingEstimate:
    """Height of horizontal bars: frame + bars × band + axes (and legend). The range is the band thickness that
    reads well (``min_band`` to ``max_band``); the recommended height uses the profile's band."""
    reasons: list[str] = []
    count, cap = _visible_rows(content.bars, max_rows, reasons, "the chart is sized for the maximum")
    count = max(1, min(count, cap))
    bars = profile.bars
    axes = bars.axes_and_legend if content.legend else bars.axes_without_legend
    band = band_px(content.labels, profile)
    if band > bars.band:
        reasons.append(f"labels wrap in more lines than fit in a {bars.band:g} px band: {band:g} px per bar")

    def height(viewport: int, per_bar: float) -> float:
        return frame_px(content.title, layout.columns, viewport, profile, layout.vertical_filter_bar) + \
            count * per_bar + axes

    low = to_units(height(profile.narrowest, max(bars.min_band, label_band_px(content.labels, profile))))
    recommended = to_units(height(profile.narrowest, band))
    high = max(recommended, to_units(height(profile.widest, max(bars.max_band, band))))
    return SizingEstimate(min_units=min(low, recommended), recommended_units=recommended, max_units=high,
                          reasons=tuple(reasons))


# ------------------------------------------------------------------------------------------------------- markdown

# Superset renders dashboard markdown with react-markdown (CommonMark) and remark-gfm (tables, strikethrough),
# raw HTML through rehype-raw (superset-ui-core SafeMarkdown): markdown-it-py follows the same CommonMark rules.
_MARKDOWN = MarkdownIt("commonmark").enable(["table", "strikethrough"])
_HTML_BREAK = re.compile(r"<br\s*/?>", re.I)
# Blocks whose rendered height the text cannot tell.
_UNMEASURABLE_BLOCKS = {"fence": "a code block", "code_block": "a code block", "table_open": "a table",
                        "html_block": "HTML other than <br>"}


@dataclass
class _Block:
    kind: str  # "p", "li", "h1".."h6" or "hr"
    text: str = ""
    bold: int = 0
    # Bold characters of each line of `text` (split at its newlines: hard breaks and <br>).
    line_bold: tuple[int, ...] = ()
    depth: int = 0  # list nesting of a list item
    # An item of a loose list (items separated by blank lines): rendered as a paragraph, with its margins.
    loose: bool = False
    list_id: int = 0  # which top-level list a list item belongs to (consecutive lists keep their margin)


@dataclass
class _Inline:
    """The rendered lines of an inline token, with the bold characters of each, and what cannot be measured."""
    lines: list[str] = field(default_factory=lambda: [""])
    bold: list[int] = field(default_factory=lambda: [0])
    strong: int = 0
    problems: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.lines[-1] += text
        self.bold[-1] += len(text) if self.strong else 0

    def new_line(self) -> None:
        self.lines.append("")
        self.bold.append(0)


def _inline(token: Token) -> _Inline:
    """Walk the children of an inline token: text, soft breaks (a space), hard breaks and <br> (a new line), bold."""
    inline = _Inline()
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            inline.add(child.content)
        elif child.type == "softbreak":
            inline.add(" ")
        elif child.type == "hardbreak" or child.type == "html_inline" and _HTML_BREAK.fullmatch(child.content.strip()):
            inline.new_line()
        elif child.type in ("strong_open", "strong_close"):
            inline.strong += 1 if child.type == "strong_open" else -1
        elif child.type == "image":
            inline.problems.append("an image")
        elif child.type == "html_inline":
            inline.problems.append("HTML other than <br>")
    return inline


def _parse_markdown(markdown: str) -> tuple[list[_Block], list[str]]:
    """The measurable blocks of the markdown, in order, and what in it cannot be measured (images, code blocks,
    tables, HTML other than <br>)."""
    blocks: list[_Block] = []
    problems: list[str] = []
    tokens = _MARKDOWN.parse(markdown or "")
    depth = list_id = 0
    for index, token in enumerate(tokens):
        if token.type in _UNMEASURABLE_BLOCKS:
            problems.append(_UNMEASURABLE_BLOCKS[token.type])
        elif token.type in ("bullet_list_open", "ordered_list_open", "bullet_list_close", "ordered_list_close"):
            list_id += token.type.endswith("_open") and depth == 0  # a new top-level list
            depth += 1 if token.type.endswith("_open") else -1
        elif token.type == "hr":
            blocks.append(_Block("hr"))
        elif token.type == "inline" and index and tokens[index - 1].type in ("heading_open", "paragraph_open"):
            opener = tokens[index - 1]
            kind = opener.tag if opener.type == "heading_open" else ("li" if depth else "p")
            inline = _inline(token)
            problems.extend(inline.problems)
            lines = [line.strip() for line in inline.lines]
            # In a tight list the paragraph token is hidden (no <p> rendered); in a loose one it is a paragraph.
            loose = kind == "li" and not opener.hidden
            blocks.append(_Block(kind, "\n".join(lines), sum(inline.bold), tuple(inline.bold), depth, loose,
                                 list_id if depth else 0))
    return blocks, problems


def _markdown_blocks(markdown: str) -> list[_Block]:
    """The measurable blocks of the markdown, in order."""
    return _parse_markdown(markdown)[0]


def _text_lines(block: _Block, style: TextStyle, width: float, markdown: MarkdownMeasures) -> tuple[int, int]:
    """(lines the block's text takes in `width` px, lines with bold text); each newline starts a line."""
    char = markdown.char_width_em * style.font
    per_line = max(1, int((width - markdown.wrap_slack_chars * char) // char))
    total = with_bold = 0
    remaining = block.bold
    parts = block.text.split("\n")
    line_bold = block.line_bold if len(block.line_bold) == len(parts) else ()
    for index, part in enumerate(parts):
        bold = min(line_bold[index] if line_bold else remaining, len(part))
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
    previous_list = 0  # list_id of the previous block (0: not a list item)
    for block in _markdown_blocks(markdown):
        if block.kind == "hr":
            height, top, bottom = measures.rule_height, measures.rule_margin, measures.rule_margin
        else:
            style = measures.styles[block.kind]
            width = usable - measures.list_indent * block.depth
            lines, with_bold = _text_lines(block, style, width, measures)
            height, top, bottom = style.line * lines + measures.bold_extra_line * with_bold, style.margin_top, \
                style.margin_bottom
            if block.loose:  # a loose list item is a paragraph inside the item
                paragraph = measures.styles["p"]
                top, bottom = max(top, paragraph.margin_top), max(bottom, paragraph.margin_bottom)
        if block.list_id != previous_list:  # entering or leaving a list, or between two lists: its margin applies
            top = max(top, measures.list_margin)
        total += max(pending_margin, top) + height
        pending_margin = bottom
        previous_list = block.list_id
    if previous_list:
        pending_margin = max(pending_margin, measures.list_margin)
    return 2 * measures.padding + total + pending_margin


def estimate_markdown(markdown: str, profile: SizingProfile, layout: Layout = FULL_WIDTH) -> SizingEstimate:
    """Height of a markdown component; text with an image (markdown or HTML), a fenced code block, a table (markdown
    or HTML) or other HTML than ``<br>`` is not measurable and gets the grid minimum with a reason."""
    reasons: list[str] = []
    problems = _parse_markdown(markdown)[1]
    if problems:
        reasons.append(f"markdown with {', '.join(sorted(set(problems)))}: not estimated")
        return SizingEstimate(GRID_MIN_ROW_UNITS, GRID_MIN_ROW_UNITS, GRID_MAX_ROW_UNITS, tuple(reasons), True)
    needed = {viewport: markdown_px(markdown, layout.columns, viewport, profile, layout.vertical_filter_bar)
              for viewport in profile.viewports}
    return _range(needed, profile, profile.max_empty, reasons, margin_units=profile.markdown_margin_units)


# ------------------------------------------------------------------------------------------- calibrated profiles

#: Superset version whose calibrated profile is used when none is given (the target of this release line).
DEFAULT_PROFILE_VERSION = "6.1.0"


@functools.cache
def calibrated_profile(version: str = DEFAULT_PROFILE_VERSION) -> SizingProfile:
    """The profile calibrated in a browser for `version` with the default theme (``profiles/`` of this package,
    written by ``bin/scripts/calibrate_sizing.py``). An instance with its own theme or CSS needs its own profile."""
    path = resources.files(__package__).joinpath("profiles").joinpath(f"sizing_profile_{version}.json")
    if not path.is_file():
        raise ValueError(f"no calibrated sizing profile for Superset {version}")
    return SizingProfile.model_validate(json.loads(path.read_text(encoding="utf-8"))["profile"])


#: What a sized component holds: the content of a table, pivot table or horizontal bars, or the markdown text.
Content = TableContent | BarsContent | str


def estimate(shape: ChartShape, content: Content, profile: SizingProfile, layout: Layout = FULL_WIDTH,
             max_rows: int | None = None) -> SizingEstimate:
    """The estimate of the formula of `shape` (``content`` must be the matching type)."""
    if shape is ChartShape.MARKDOWN and isinstance(content, str):
        return estimate_markdown(content, profile, layout)
    if shape is ChartShape.HORIZONTAL_BARS and isinstance(content, BarsContent):
        return estimate_horizontal_bars(content, profile, layout, max_rows)
    if shape is ChartShape.TABLE and isinstance(content, TableContent):
        return estimate_table(content, profile, layout, max_rows)
    if shape is ChartShape.PIVOT_TABLE and isinstance(content, TableContent):
        return estimate_pivot_table(content, profile, layout, max_rows)
    raise TypeError(f"{type(content).__name__} is not the content of a {shape} component")

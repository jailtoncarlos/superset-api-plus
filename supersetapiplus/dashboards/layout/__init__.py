"""Dashboard layout (`position_json`): lossless round trip and a builder that mirrors the Superset editor.

The layout is kept as the flat component map Superset stores (``{id: {id, type, children, parents,
meta}}`` plus ``DASHBOARD_VERSION_KEY``). Reading and writing it back never adds, drops or reorders
keys; the builder methods only touch the components they create. Constants and component rules follow
``superset-frontend/src/dashboard/util/constants.ts`` and ``componentTypes.ts`` (Superset 6.1.0).
"""
from __future__ import annotations

import copy
import warnings
from dataclasses import dataclass, replace
from typing import Any, Literal, TypeAlias

import shortuuid
from pydantic import Field, PrivateAttr, SerializationInfo, SerializerFunctionWrapHandler, model_serializer, model_validator

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.enums import StringEnum
from supersetapiplus.core.references import SavedChart
from supersetapiplus.dashboards.layout import sizing
from supersetapiplus.dashboards.layout.sizing import (
    BarsContent,
    ChartShape,
    SizingEstimate,
    SizingMode,
    SizingProfile,
    TableContent,
)
from supersetapiplus.dashboards.layout.validation import layout_problems
from supersetapiplus.exceptions import LayoutWarning, NodePositionValidationError, SizingError, SizingWarning

ROOT_ID = "ROOT_ID"
GRID_ID = "GRID_ID"
HEADER_ID = "HEADER_ID"
VERSION_KEY = "DASHBOARD_VERSION_KEY"
LAYOUT_VERSION = "v2"
# Grid limits of the dashboard editor (superset-frontend/src/dashboard/util/constants.ts, Superset 6.1.0).
# Superset does not validate position_json on save, so the builder enforces what the editor can produce.
GRID_COLUMN_COUNT = 12
GRID_MIN_COLUMN_COUNT = 1
GRID_MIN_ROW_UNITS = 5
GRID_MAX_ROW_UNITS = 100
DEFAULT_CHART_WIDTH = 4
DEFAULT_HEIGHT = 50


class ComponentType(StringEnum):
    ROOT = "ROOT"
    GRID = "GRID"
    HEADER = "HEADER"
    TABS = "TABS"
    TAB = "TAB"
    ROW = "ROW"
    COLUMN = "COLUMN"
    CHART = "CHART"
    MARKDOWN = "MARKDOWN"
    DIVIDER = "DIVIDER"
    DYNAMIC = "DYNAMIC"


class Background(StringEnum):
    TRANSPARENT = "BACKGROUND_TRANSPARENT"
    WHITE = "BACKGROUND_WHITE"


class HeaderSize(StringEnum):
    SMALL = "SMALL_HEADER"
    MEDIUM = "MEDIUM_HEADER"
    LARGE = "LARGE_HEADER"


# Components each container accepts when building from code.
_ALLOWED_CHILDREN = {
    "ROOT": {"GRID", "TABS"},
    "GRID": {"ROW", "TABS", "HEADER", "DIVIDER"},
    "TABS": {"TAB"},
    "TAB": {"ROW", "TABS", "HEADER", "DIVIDER"},
    "ROW": {"CHART", "MARKDOWN", "COLUMN"},
    "COLUMN": {"ROW", "CHART", "MARKDOWN", "HEADER", "DIVIDER"},
}


@dataclass(frozen=True)
class ChartRef:
    """Reference to a chart already saved in Superset, for placing it in a layout without loading it."""
    id: int
    slice_name: str
    uuid: str | None = None


@dataclass(frozen=True)
class LayoutComponent:
    """Handle to a component of a :class:`DashboardLayout`; pass it as ``parent`` to the ``add_*`` methods."""
    layout: DashboardLayout
    id: str

    @property
    def data(self) -> dict[str, Any]:
        return self.layout.components[self.id]

    @property
    def type(self) -> str:
        return str(self.data["type"])

    @property
    def meta(self) -> dict[str, Any]:
        meta: dict[str, Any] = self.data.setdefault("meta", {})
        return meta

    @property
    def children(self) -> list[LayoutComponent]:
        return [LayoutComponent(self.layout, child) for child in self.data.get("children", [])]


#: Where a component goes: a component returned by the ``add_*`` methods, a component id, or None (the default
#: place of each method, e.g. the grid).
LayoutParent: TypeAlias = LayoutComponent | str | None

#: Height of a chart or markdown component: grid row units, or "auto" (estimated from its content).
Height: TypeAlias = int | Literal["auto"]


@dataclass(frozen=True)
class _SizingHint:
    """What the library knows of a component's content, kept outside ``position_json``."""
    shape: ChartShape
    content: sizing.Content
    max_rows: int | None = None


class DashboardLayout(ApiModel):
    """`position_json` of a dashboard: the flat component map, its version and any other key Superset stored."""
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # default_factory: a layout read without a version stays without one.
    version: Any = Field(default_factory=lambda: LAYOUT_VERSION)

    # True for layouts started by the library (empty()): their title header follows the dashboard title.
    _created_by_library: bool = PrivateAttr(default=False)
    # Content of the components placed with it (add_chart(content=...), add_markdown), by component id: never
    # written to position_json.
    _sizing_hints: dict[str, _SizingHint] = PrivateAttr(default_factory=dict)
    _sizing: SizingMode = PrivateAttr(default=SizingMode.WARN)
    _sizing_profile: SizingProfile | None = PrivateAttr(default=None)

    @property
    def created_by_library(self) -> bool:
        return self._created_by_library

    @created_by_library.setter
    def created_by_library(self, value: bool) -> None:
        self._created_by_library = value

    @property
    def sizing(self) -> SizingMode:
        """Check, when the layout is sent, of the components placed with their content: ``"warn"`` (default, a
        SizingWarning), ``"strict"`` (a SizingError; pivot tables only warn) or ``"off"``."""
        return self._sizing

    @sizing.setter
    def sizing(self, value: SizingMode | str) -> None:
        self._sizing = SizingMode(value)

    @property
    def sizing_profile(self) -> SizingProfile:
        """Measures used by ``height="auto"`` and the sizing check: the calibrated profile of the target Superset
        version with the default theme, unless another one is set (an instance with its own theme or CSS)."""
        return self._sizing_profile or sizing.calibrated_profile()

    @sizing_profile.setter
    def sizing_profile(self, value: SizingProfile | None) -> None:
        self._sizing_profile = value

    # --- construction and serialization -----------------------------------------------------

    @classmethod
    def empty(cls, title: str = "") -> DashboardLayout:
        """Layout of a new dashboard, as created by the Superset editor (root, grid and title header)."""
        layout = cls(components={
            ROOT_ID: {"type": "ROOT", "id": ROOT_ID, "children": [GRID_ID]},
            GRID_ID: {"type": "GRID", "id": GRID_ID, "children": [], "parents": [ROOT_ID]},
            HEADER_ID: {"id": HEADER_ID, "type": "HEADER", "meta": {"text": title}},
        })
        layout.created_by_library = True
        return layout

    @model_validator(mode="before")
    @classmethod
    def _from_flat_map(cls, data: Any) -> Any:
        """The map Superset stores: components (dicts) by id, the version key and other keys (kept as read)."""
        if not isinstance(data, dict) or "components" in data:
            return data
        components = {key: copy.deepcopy(value) for key, value in data.items() if isinstance(value, dict)}
        others = {key: value for key, value in data.items() if not isinstance(value, dict) and key != VERSION_KEY}
        return {**others, "components": components, "version": data.get(VERSION_KEY)}

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> Any:
        if not isinstance(self, DashboardLayout):
            return self
        data: dict[str, Any] = {} if self.version is None else {VERSION_KEY: self.version}
        data.update(copy.deepcopy(self.components))
        data.update(self.extra_fields)
        return data

    def problems(self) -> list[str]:
        """Rules of the dashboard renderer the layout breaks (types, nesting depth, cycles, reachability).

        For layouts built by the library, stored ``parents`` must also match the real path (they define the
        native filter scopes); layouts read from Superset may carry stale ones, as the editor saves them.
        """
        return layout_problems(self.components, check_parents=self.created_by_library)

    def validate(self) -> None:  # type: ignore[override]  # the facade method, not the deprecated classmethod
        """Raises NodePositionValidationError listing every problem (see :meth:`problems`)."""
        problems = self.problems()
        if problems:
            raise NodePositionValidationError("Invalid dashboard layout: " + " ".join(problems))

    def _check_before_sending(self) -> None:
        """A layout built by the library must be valid; one read from Superset is sent as read, with a warning.
        Components placed with their content are checked against it (:attr:`sizing`)."""
        self._check_sizing()
        if self.created_by_library:
            self.validate()
            return
        problems = self.problems()
        if problems:
            warnings.warn("Dashboard layout read from Superset breaks renderer rules: " + " ".join(problems),
                          LayoutWarning, stacklevel=2)

    def sizing_problems(self) -> list[tuple[str, SizingEstimate, str]]:
        """(component id, estimate, problem) of each component placed with its content whose height does not fit
        it (see :mod:`supersetapiplus.dashboards.layout.sizing`)."""
        found = []
        for component_id, hint in self._sizing_hints.items():
            meta = self.components.get(component_id, {}).get("meta", {})
            height, width = meta.get("height"), meta.get("width")
            if not isinstance(height, int) or not isinstance(width, int):
                continue
            code = meta.get("code")
            if hint.shape is ChartShape.MARKDOWN and isinstance(code, str):
                hint = replace(hint, content=code)  # the current text, also when edited after placing it
            estimate = self._estimate(hint, width)
            problem = estimate.problem(height)
            if problem:
                found.append((component_id, estimate, problem))
        return found

    def chart_height(self, chart: SavedChart, height: Height, width: int,
                     content: TableContent | BarsContent | None = None,
                     max_rows: int | None = None) -> tuple[_SizingHint | None, int]:
        """The content hint and grid units of a chart placed with these options; raises
        NodePositionValidationError as :meth:`add_chart` would (e.g. to check before creating the chart)."""
        hint = None if content is None else _SizingHint(_shape_of(chart, content), content, max_rows)
        units = self._height(height, hint, width)
        assert units is not None  # a chart always has a height
        _check_size(width, units)
        return hint, units

    def _check_sizing(self) -> None:
        if self.sizing is SizingMode.OFF:
            return
        errors = []
        for component_id, estimate, problem in self.sizing_problems():
            meta = self.components[component_id]["meta"]
            name = meta.get("sliceNameOverride") or meta.get("sliceName") or f"markdown {component_id}"
            message = f"{name}: {problem}" + "".join(f"; {reason}" for reason in estimate.reasons)
            if self.sizing is SizingMode.STRICT and not estimate.approximate:
                errors.append(message)
            else:
                warnings.warn(message, SizingWarning, stacklevel=4)
        if errors:
            raise SizingError("Heights that do not fit their content: " + " ".join(errors),
                              'Use height="auto", change the height or set position_json.sizing = "warn".')

    def _estimate(self, hint: _SizingHint, width: int) -> SizingEstimate:
        return sizing.estimate(hint.shape, hint.content, self.sizing_profile, sizing.Layout(columns=width),
                               hint.max_rows)

    def _height(self, height: Height | None, hint: _SizingHint | None, width: int) -> int | None:
        """Grid units of `height`; "auto" is the recommended height of the content."""
        if height != "auto":
            return None if height is None else int(height)
        if hint is None:
            raise NodePositionValidationError('height="auto" needs the content of the chart (content=...).')
        estimate = self._estimate(hint, width)
        if estimate.approximate and hint.shape is ChartShape.MARKDOWN:
            raise NodePositionValidationError("The markdown cannot be sized automatically (" +
                                              "; ".join(estimate.reasons) + "): give its height.")
        return estimate.recommended_units

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DashboardLayout):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    @property
    def tree(self) -> DashboardLayout:
        """Deprecated: the layout used to be a `MetadataPosition` wrapping a tree; use the layout itself."""
        warnings.warn("position_json.tree is deprecated; call the methods on position_json directly.",
                      DeprecationWarning, stacklevel=2)
        return self

    # --- queries ------------------------------------------------------------------------------

    def find_by_id(self, component_id: str) -> LayoutComponent | None:
        return LayoutComponent(self, component_id) if component_id in self.components else None

    def components_of_type(self, component_type: ComponentType | str) -> list[LayoutComponent]:
        wanted = str(component_type)
        return [LayoutComponent(self, cid) for cid, data in self.components.items() if data.get("type") == wanted]

    def find_tab(self, title: str) -> LayoutComponent | None:
        return next((tab for tab in self.components_of_type(ComponentType.TAB) if tab.meta.get("text") == title), None)

    def chart_ids(self) -> list[int]:
        """Ids of the charts in the layout, in tree order."""
        ids: list[int] = []

        def visit(component_id: str) -> None:
            component = self.components.get(component_id, {})
            if component.get("type") == "CHART":
                ids.append(component.get("meta", {}).get("chartId"))
            for child in component.get("children", []):
                visit(child)

        visit(ROOT_ID)
        return ids

    def charts_and_tabs_in_scope(self, root_path: list[str], excluded: list[int]) -> tuple[list[int], list[str]]:
        """Charts with an ancestor in `root_path`, minus `excluded`, and the tabs that contain them.

        Same rule as ``getChartIdsInFilterScope`` and ``findTabsWithChartsInScope`` in the frontend.
        """
        charts: list[int] = []
        tabs: list[str] = []
        for component in self.components.values():
            chart_id = component.get("meta", {}).get("chartId")
            parents = component.get("parents") or []
            if component.get("type") != "CHART" or chart_id in excluded or chart_id in charts:
                continue
            if not any(parent in root_path for parent in parents):
                continue
            charts.append(chart_id)
            tabs.extend(p for p in parents if p.startswith("TAB-") and p not in tabs)
        return charts, tabs

    # --- builder ------------------------------------------------------------------------------

    def set_title(self, title: str) -> None:
        if HEADER_ID in self.components:
            self.components[HEADER_ID].setdefault("meta", {})["text"] = title

    def add_tabs(self, parent: LayoutParent = None, id: str | None = None) -> LayoutComponent:
        """Tabs container. Without `parent`, top-level tabs go inside the grid (ROOT → GRID → TABS)."""
        return self._add("TABS", parent or GRID_ID, {}, id)

    def add_tab(self, title: str, parent: LayoutParent = None, id: str | None = None) -> LayoutComponent:
        """Tab inside a TABS container; without `parent`, uses the last top-level TABS (creating it if needed)."""
        if parent is None:
            grid = self.find_by_id(GRID_ID)
            grid_tabs = [c for c in grid.children if c.type == "TABS"] if grid else []
            parent = grid_tabs[-1] if grid_tabs else self.add_tabs()
        return self._add("TAB", parent, {"text": title}, id)

    def add_row(self, parent: LayoutParent = None, background: Background | str = Background.TRANSPARENT,
                id: str | None = None) -> LayoutComponent:
        return self._add("ROW", parent or GRID_ID, {"background": str(background)}, id)

    def add_header(self, text: str, parent: LayoutParent = None, size: HeaderSize | str = HeaderSize.MEDIUM,
                   background: Background | str = Background.TRANSPARENT, id: str | None = None) -> LayoutComponent:
        meta = {"text": text, "headerSize": str(size), "background": str(background)}
        return self._add("HEADER", parent or GRID_ID, meta, id)

    def add_divider(self, parent: LayoutParent = None, id: str | None = None) -> LayoutComponent:
        return self._add("DIVIDER", parent or GRID_ID, {}, id)

    def add_markdown(self, code: str, parent: LayoutParent = None, height: Height | None = DEFAULT_HEIGHT,
                     width: int = DEFAULT_CHART_WIDTH,
                     id: str | None = None) -> LayoutComponent:
        """Markdown block; ``height=None`` omits the height from ``meta``, as some exports do, and ``"auto"`` sizes
        it from the text. Its height is checked against the text when the layout is sent (:attr:`sizing`)."""
        hint = _SizingHint(ChartShape.MARKDOWN, code)
        units = self._height(height, hint, width)
        _check_size(width, units)
        meta: dict[str, Any] = {"code": code, "width": width}
        if units is not None:
            meta["height"] = units
        component = self._add("MARKDOWN", self._row_for(parent, width), meta, id)
        self._set_hint(component.id, hint)
        return component

    def add_column(self, parent: LayoutParent = None, width: int = DEFAULT_CHART_WIDTH,
                   background: Background | str = Background.TRANSPARENT, id: str | None = None) -> LayoutComponent:
        """Column (charts, markdown and rows stacked vertically) of `width` grid columns.

        Like the editor, a column lives in a ROW: inside a grid or tab it goes into the last row with room
        (``newComponentFactory``: ``{width, background}``). Components placed in it are at most as wide as it.
        """
        _check_size(width, None)
        return self._add("COLUMN", self._row_for(parent, width), {"width": width, "background": str(background)}, id)

    def add_chart(self, chart: SavedChart, title: str | None = None, parent: LayoutParent = None,
                  height: Height = DEFAULT_HEIGHT, width: int = DEFAULT_CHART_WIDTH, id: str | None = None,
                  skip_existing: bool = False, content: TableContent | BarsContent | None = None,
                  max_rows: int | None = None) -> LayoutComponent:
        """Place a saved chart (a library Chart or a :class:`ChartRef`); `title` becomes ``sliceNameOverride``.

        With ``skip_existing=True`` a chart already in the layout is not placed again: its component is returned.
        `content` describes a table, pivot table or horizontal bars chart (rows or bars, labels, title): with it,
        ``height="auto"`` gives the height its content needs (at most `max_rows` rows or bars are shown), and the
        height is checked when the layout is sent (:attr:`sizing`). The content is kept by the library, never
        written to ``position_json``.
        """
        chart_id = chart.id
        if not chart_id:
            raise NodePositionValidationError("Save the chart before placing it in a layout (chart.id is empty).")
        existing = self._chart_components(chart_id) if skip_existing else []
        if existing:
            return existing[0]
        hint, units = self.chart_height(chart, height, width, content, max_rows)
        meta: dict[str, Any] = {"chartId": chart_id, "sliceName": chart.slice_name, "width": width, "height": units}
        uuid = getattr(chart, "uuid", None)
        if uuid:
            meta["uuid"] = str(uuid)
        if title and title != chart.slice_name:
            meta["sliceNameOverride"] = title
        component = self._add("CHART", self._row_for(parent, width), meta, id)
        self._set_hint(component.id, hint)
        return component

    def add_chart_grid(self, charts: list[SavedChart], columns: int = 2, parent: LayoutParent = None,
                       height: int = DEFAULT_HEIGHT) -> list[LayoutComponent]:
        """Places `charts` in new rows of `columns` charts each, every chart ``12 // columns`` grid columns wide."""
        if not 1 <= columns <= GRID_COLUMN_COUNT:
            raise NodePositionValidationError(f"columns must be 1 to {GRID_COLUMN_COUNT}, not {columns}.")
        width = GRID_COLUMN_COUNT // columns
        placed: list[LayoutComponent] = []
        for start in range(0, len(charts), columns):
            row = self.add_row(parent)
            placed.extend(self.add_chart(chart, parent=row, height=height, width=width)
                          for chart in charts[start:start + columns])
        return placed

    def add_chart_tabs(self, tabs: dict[str, list[SavedChart]], columns: int = 2, parent: LayoutParent = None,
                       height: int = DEFAULT_HEIGHT) -> dict[str, LayoutComponent]:
        """A TABS container with one tab per title, each holding its charts in a grid (see add_chart_grid)."""
        container = self.add_tabs(parent)
        created: dict[str, LayoutComponent] = {}
        for title, charts in tabs.items():
            created[title] = self.add_tab(title, parent=container)
            self.add_chart_grid(charts, columns, parent=created[title], height=height)
        return created

    def remove_chart(self, chart: SavedChart | int) -> int:
        """Removes every placement of `chart` (a chart, a ChartRef or a chart id) and the rows and columns left
        empty; returns how many placements were removed. The paths (`parents`) of the other components stay."""
        chart_id = chart if isinstance(chart, int) else chart.id
        if chart_id is None:  # a chart never saved has no placement
            return 0
        removed = self._chart_components(chart_id)
        for component in removed:
            self._remove(component.id)
        return len(removed)

    def _chart_components(self, chart_id: int) -> list[LayoutComponent]:
        return [c for c in self.components_of_type(ComponentType.CHART) if c.meta.get("chartId") == chart_id]

    def _remove(self, component_id: str) -> None:
        """Removes a leaf component, then its ROW or COLUMN ancestors that become empty."""
        while True:
            parent_id = next((cid for cid, data in self.components.items()
                              if component_id in (data.get("children") or [])), None)
            del self.components[component_id]
            self._sizing_hints.pop(component_id, None)
            if parent_id is None:
                return
            siblings = self.components[parent_id]["children"]
            siblings.remove(component_id)
            if siblings or self.components[parent_id]["type"] not in ("ROW", "COLUMN"):
                return
            component_id = parent_id

    def _set_hint(self, component_id: str, hint: _SizingHint | None) -> None:
        """The content of a new component; none clears what an earlier component with the same id left."""
        if hint is None:
            self._sizing_hints.pop(component_id, None)
        else:
            self._sizing_hints[component_id] = hint

    def _row_for(self, parent: LayoutParent, width: int) -> str:
        """Charts and markdown live in a ROW or COLUMN; inside a grid or tab, reuse its last row with room."""
        parent_id = self._resolve(parent or GRID_ID)
        if self.components[parent_id]["type"] in ("ROW", "COLUMN"):
            self._check_room(parent_id, width)
            return parent_id
        rows = [c for c in self.components[parent_id].get("children", []) if self.components[c]["type"] == "ROW"]
        if rows and self._row_width(rows[-1]) + width <= GRID_COLUMN_COUNT:
            return str(rows[-1])
        return self.add_row(parent_id).id

    def _check_room(self, container_id: str, width: int) -> None:
        """A row holds at most 12 grid columns; a component in a column is at most as wide as the column."""
        container = self.components[container_id]
        if container["type"] == "COLUMN":
            column_width = container.get("meta", {}).get("width", GRID_COLUMN_COUNT)
            if width > column_width:
                raise NodePositionValidationError(
                    f"A component of width {width} does not fit in column {container_id} of width {column_width}.")
        elif self._row_width(container_id) + width > GRID_COLUMN_COUNT:
            raise NodePositionValidationError(
                f"There is not enough space for this component. Total {self._row_width(container_id) + width} "
                f"exceeds the maximum allowable width of {GRID_COLUMN_COUNT}.")

    def _row_width(self, row_id: str) -> int:
        return sum(self.components[c].get("meta", {}).get("width", 0) for c in self.components[row_id].get("children", []))

    def _resolve(self, parent: LayoutParent) -> str:
        parent_id = parent.id if isinstance(parent, LayoutComponent) else str(parent)
        if parent_id not in self.components:
            raise NodePositionValidationError(f"Unknown parent component {parent_id}.")
        return parent_id

    def _add(self, component_type: str, parent: LayoutParent, meta: dict[str, Any],
             component_id: str | None) -> LayoutComponent:
        parent_id = self._resolve(parent)
        parent_data = self.components[parent_id]
        if component_type not in _ALLOWED_CHILDREN.get(parent_data["type"], set()):
            raise NodePositionValidationError(f"{parent_data['type']} does not accept a {component_type} child.")
        component_id = component_id or f"{component_type}-{shortuuid.ShortUUID().random(length=10)}"
        if component_id in self.components:
            raise NodePositionValidationError(f"Component id {component_id} already exists.")
        self.components[component_id] = {
            "children": [],
            "id": component_id,
            "meta": meta,
            "parents": [*parent_data.get("parents", []), parent_id],
            "type": component_type,
        }
        parent_data.setdefault("children", []).append(component_id)
        return LayoutComponent(self, component_id)


def _shape_of(chart: SavedChart, content: TableContent | BarsContent) -> ChartShape:
    """The sizing formula of a chart: from its params when it has them (a library Chart), else from the content
    (a ChartRef: tables and horizontal bars; place a pivot table with the chart itself)."""
    params = getattr(chart, "params", None)
    if params is None:
        return ChartShape.HORIZONTAL_BARS if isinstance(content, BarsContent) else ChartShape.TABLE
    viz_type = str(getattr(params, "viz_type", "") or "")
    shape = sizing.chart_shape({"viz_type": viz_type, "orientation": str(getattr(params, "orientation", "") or "")})
    expected = (ChartShape.HORIZONTAL_BARS,) if isinstance(content, BarsContent) else (ChartShape.TABLE,
                                                                                       ChartShape.PIVOT_TABLE)
    if shape is None or shape not in expected:
        raise NodePositionValidationError(
            f"{type(content).__name__} describes {' or '.join(map(str, expected))}, not a {viz_type} chart"
            + ("" if shape else " (the sizing formulas cover tables, pivot tables and horizontal bars)") + ".")
    return shape


def _check_size(width: int, height: int | None) -> None:
    """Width in grid columns and height in grid row units, within the limits of the dashboard editor."""
    if not GRID_MIN_COLUMN_COUNT <= width <= GRID_COLUMN_COUNT:
        raise NodePositionValidationError(
            f"Width {width} is out of the grid: use {GRID_MIN_COLUMN_COUNT} to {GRID_COLUMN_COUNT} columns.")
    if height is not None and not GRID_MIN_ROW_UNITS <= height <= GRID_MAX_ROW_UNITS:
        raise NodePositionValidationError(
            f"Height {height} is out of the grid: use {GRID_MIN_ROW_UNITS} to {GRID_MAX_ROW_UNITS} row units.")

"""Dashboard layout (`position_json`): lossless round trip and a builder that mirrors the Superset editor.

The layout is kept as the flat component map Superset stores (``{id: {id, type, children, parents,
meta}}`` plus ``DASHBOARD_VERSION_KEY``). Reading and writing it back never adds, drops or reorders
keys; the builder methods only touch the components they create. Constants and component rules follow
``superset-frontend/src/dashboard/util/constants.ts`` and ``componentTypes.ts`` (Superset 6.1.0).
"""
from __future__ import annotations

import copy
import warnings
from dataclasses import dataclass
from typing import Any

import shortuuid

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.enum_str import StringEnum
from supersetapiplus.exceptions import NodePositionValidationError

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
    def data(self) -> dict:
        return self.layout.components[self.id]

    @property
    def type(self) -> str:
        return self.data["type"]

    @property
    def meta(self) -> dict:
        return self.data.setdefault("meta", {})

    @property
    def children(self) -> list[LayoutComponent]:
        return [LayoutComponent(self.layout, child) for child in self.data.get("children", [])]


class DashboardLayout(SerializableModel):
    """`position_json` of a dashboard."""

    def __init__(self, components: dict | None = None, version: Any = LAYOUT_VERSION, **kwargs):
        self.components: dict[str, dict] = components if components is not None else {}
        self.version = version
        self._extra_fields = {}
        # True for layouts started by the library (empty()): their title header follows the dashboard title.
        self.created_by_library = False

    # --- construction and serialization -----------------------------------------------------

    @classmethod
    def empty(cls, title: str = "") -> DashboardLayout:
        """Layout of a new dashboard, as created by the Superset editor (root, grid and title header)."""
        layout = cls({
            ROOT_ID: {"type": "ROOT", "id": ROOT_ID, "children": [GRID_ID]},
            GRID_ID: {"type": "GRID", "id": GRID_ID, "children": [], "parents": [ROOT_ID]},
            HEADER_ID: {"id": HEADER_ID, "type": "HEADER", "meta": {"text": title}},
        })
        layout.created_by_library = True
        return layout

    @classmethod
    def from_json(cls, data: dict) -> DashboardLayout:
        data = data or {}
        components = {key: copy.deepcopy(value) for key, value in data.items() if isinstance(value, dict)}
        layout = cls(components, data.get(VERSION_KEY))
        layout._extra_fields = {k: v for k, v in data.items() if not isinstance(v, dict) and k != VERSION_KEY}
        return layout

    def to_dict(self, columns: list = None, convert_to_json: bool = False) -> dict:
        data: dict = {}
        if self.version is not None:
            data[VERSION_KEY] = self.version
        data.update(copy.deepcopy(self.components))
        data.update(self._extra_fields)
        return data

    def validate(self):
        for component in self.components.values():
            for child in component.get("children", []):
                if child not in self.components:
                    raise NodePositionValidationError(f"{component['id']} has unknown child {child}.")

    def __eq__(self, other):
        if not isinstance(other, DashboardLayout):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    __hash__ = None

    @property
    def tree(self) -> DashboardLayout:
        """Deprecated: the layout used to be a `Metadataposition` wrapping a tree; use the layout itself."""
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

    def add_tabs(self, parent=None, id: str | None = None) -> LayoutComponent:
        """Tabs container. Without `parent`, top-level tabs go inside the grid (ROOT → GRID → TABS)."""
        return self._add("TABS", parent or GRID_ID, {}, id)

    def add_tab(self, title: str, parent=None, id: str | None = None) -> LayoutComponent:
        """Tab inside a TABS container; without `parent`, uses the last top-level TABS (creating it if needed)."""
        if parent is None:
            grid_tabs = [c for c in self.find_by_id(GRID_ID).children if c.type == "TABS"]
            parent = grid_tabs[-1] if grid_tabs else self.add_tabs()
        return self._add("TAB", parent, {"text": title}, id)

    def add_row(self, parent=None, background: Background | str = Background.TRANSPARENT,
                id: str | None = None) -> LayoutComponent:
        return self._add("ROW", parent or GRID_ID, {"background": str(background)}, id)

    def add_header(self, text: str, parent=None, size: HeaderSize | str = HeaderSize.MEDIUM,
                   background: Background | str = Background.TRANSPARENT, id: str | None = None) -> LayoutComponent:
        meta = {"text": text, "headerSize": str(size), "background": str(background)}
        return self._add("HEADER", parent or GRID_ID, meta, id)

    def add_divider(self, parent=None, id: str | None = None) -> LayoutComponent:
        return self._add("DIVIDER", parent or GRID_ID, {}, id)

    def add_markdown(self, code: str, parent=None, height: int | None = DEFAULT_HEIGHT, width: int = DEFAULT_CHART_WIDTH,
                     id: str | None = None) -> LayoutComponent:
        """Markdown block; ``height=None`` omits the height from ``meta``, as some exports do."""
        _check_size(width, height)
        meta: dict = {"code": code, "width": width}
        if height is not None:
            meta["height"] = height
        return self._add("MARKDOWN", self._row_for(parent, width), meta, id)

    def add_chart(self, chart, title: str | None = None, parent=None, height: int = DEFAULT_HEIGHT,
                  width: int = DEFAULT_CHART_WIDTH, id: str | None = None) -> LayoutComponent:
        """Place a saved chart (a library Chart or a :class:`ChartRef`); `title` becomes ``sliceNameOverride``."""
        if not getattr(chart, "id", None):
            raise NodePositionValidationError("Save the chart before placing it in a layout (chart.id is empty).")
        _check_size(width, height)
        meta: dict = {"chartId": chart.id, "sliceName": chart.slice_name, "width": width, "height": height}
        uuid = getattr(chart, "uuid", None)
        if uuid:
            meta["uuid"] = str(uuid)
        if title and title != chart.slice_name:
            meta["sliceNameOverride"] = title
        return self._add("CHART", self._row_for(parent, width), meta, id)

    def _row_for(self, parent, width: int):
        """Charts and markdown live in a ROW or COLUMN; inside a grid or tab, reuse its last row with room."""
        parent_id = self._resolve(parent or GRID_ID)
        if self.components[parent_id]["type"] in ("ROW", "COLUMN"):
            if self.components[parent_id]["type"] == "ROW" and self._row_width(parent_id) + width > GRID_COLUMN_COUNT:
                raise NodePositionValidationError(
                    f"There is not enough space for this component. Total {self._row_width(parent_id) + width} "
                    f"exceeds the maximum allowable width of {GRID_COLUMN_COUNT}.")
            return parent_id
        rows = [c for c in self.components[parent_id].get("children", []) if self.components[c]["type"] == "ROW"]
        if rows and self._row_width(rows[-1]) + width <= GRID_COLUMN_COUNT:
            return rows[-1]
        return self.add_row(parent_id).id

    def _row_width(self, row_id: str) -> int:
        return sum(self.components[c].get("meta", {}).get("width", 0) for c in self.components[row_id].get("children", []))

    def _resolve(self, parent) -> str:
        parent_id = parent.id if isinstance(parent, LayoutComponent) else str(parent)
        if parent_id not in self.components:
            raise NodePositionValidationError(f"Unknown parent component {parent_id}.")
        return parent_id

    def _add(self, component_type: str, parent, meta: dict, component_id: str | None) -> LayoutComponent:
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


def _check_size(width: int, height: int | None) -> None:
    """Width in grid columns and height in grid row units, within the limits of the dashboard editor."""
    if not GRID_MIN_COLUMN_COUNT <= width <= GRID_COLUMN_COUNT:
        raise NodePositionValidationError(
            f"Width {width} is out of the grid: use {GRID_MIN_COLUMN_COUNT} to {GRID_COLUMN_COUNT} columns.")
    if height is not None and not GRID_MIN_ROW_UNITS <= height <= GRID_MAX_ROW_UNITS:
        raise NodePositionValidationError(
            f"Height {height} is out of the grid: use {GRID_MIN_ROW_UNITS} to {GRID_MAX_ROW_UNITS} row units.")

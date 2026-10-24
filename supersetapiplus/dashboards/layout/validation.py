"""Structural rules of a dashboard layout (`position_json`), as the Superset dashboard renders it.

The parent/child table and the nesting depths are those of ``superset-frontend/src/dashboard/util/
isValidChild.ts`` (Superset 6.1.0): TABS and TAB do not increase the depth of their children (``Tab.tsx``,
``Tabs.tsx``). The graph walk follows ``superset/mcp_service/dashboard/layout_validation.py`` (Apache
Superset, Apache-2.0), the server-side port of the same rules.

:func:`layout_problems` lists every problem found instead of stopping at the first one. Stored ``parents``
are compared with the real path only on request: Superset itself saves stale ones after a drag and drop in
the editor (three of the 6.1.0 example dashboards have them), and the frontend keeps them as stored.
"""
from __future__ import annotations

from typing import Any

ROOT_ID = "ROOT_ID"
GRID_ID = "GRID_ID"
HEADER_ID = "HEADER_ID"
ROOT_DEPTH = 0

# parentMaxDepthLookup: for each parent type, the child types it accepts and the deepest the parent may be.
PARENT_MAX_DEPTH: dict[str, dict[str, int]] = {
    "ROOT": {"GRID": ROOT_DEPTH, "TABS": ROOT_DEPTH},
    "GRID": dict.fromkeys(("CHART", "DYNAMIC", "MARKDOWN", "COLUMN", "DIVIDER", "HEADER", "ROW", "TABS"),
                          ROOT_DEPTH + 1),
    "ROW": dict.fromkeys(("CHART", "DYNAMIC", "MARKDOWN", "COLUMN"), ROOT_DEPTH + 4),
    "TABS": {"TAB": ROOT_DEPTH + 3},
    "TAB": {"CHART": ROOT_DEPTH + 5, "DYNAMIC": ROOT_DEPTH + 5, "MARKDOWN": ROOT_DEPTH + 5,
            "COLUMN": ROOT_DEPTH + 3, "DIVIDER": ROOT_DEPTH + 5, "HEADER": ROOT_DEPTH + 5,
            "ROW": ROOT_DEPTH + 3, "TABS": ROOT_DEPTH + 3},
    "COLUMN": {"CHART": ROOT_DEPTH + 5, "HEADER": ROOT_DEPTH + 5, "MARKDOWN": ROOT_DEPTH + 5,
               "ROW": ROOT_DEPTH + 3, "DIVIDER": ROOT_DEPTH + 3, "TABS": ROOT_DEPTH + 3},
    "CHART": {},
    "DYNAMIC": {},
    "DIVIDER": {},
    "HEADER": {},
    "MARKDOWN": {},
}
DEPTH_TRANSPARENT_TYPES = frozenset({"TABS", "TAB"})


def layout_problems(components: dict[str, dict[str, Any]], check_parents: bool = False) -> list[str]:
    """Problems of a flat component map (``{id: {id, type, children, parents, meta}}``); empty when valid.

    An empty map is valid: the dashboard starts from the default layout (``hydrate.ts``, ``getEmptyLayout``).
    """
    if not components:
        return []
    problems = _shape_problems(components)
    if problems:
        return problems
    problems = _edge_problems(components)
    cycle = _find_cycle(components)
    if cycle:
        return [*problems, f"The layout has a cycle at {cycle}."]
    root = components.get(ROOT_ID)
    if root is None or root.get("type") != "ROOT":
        return [*problems, f"The layout has no {ROOT_ID} component of type ROOT."]
    if len(root.get("children") or []) != 1:
        problems.append(f"{ROOT_ID} must contain exactly one GRID or TABS component.")
    reachable, walk_problems = _walk(components, check_parents)
    return [*problems, *walk_problems, *_unreachable_problems(components, reachable)]


def _shape_problems(components: dict[str, dict[str, Any]]) -> list[str]:
    problems = []
    for component_id, component in components.items():
        component_type = component.get("type")
        if component.get("id") != component_id:
            problems.append(f"Component {component_id} has a different id ({component.get('id')}).")
        if component_type not in PARENT_MAX_DEPTH:
            problems.append(f"Component {component_id} has an unknown type {component_type!r}.")
            continue
        children = component.get("children")
        if children is not None and (not isinstance(children, list)
                                     or not all(isinstance(child, str) for child in children)):
            problems.append(f"Component {component_id}: children must be a list of component ids.")
        elif children and not PARENT_MAX_DEPTH[component_type]:
            problems.append(f"Component {component_id} ({component_type}) cannot have children.")
        elif component_type == "TABS" and not children:
            problems.append(f"Tabs {component_id} must contain at least one tab.")
    return problems


def _edge_problems(components: dict[str, dict[str, Any]]) -> list[str]:
    problems = []
    parent_of: dict[str, str] = {}
    for parent_id, parent in components.items():
        accepted = PARENT_MAX_DEPTH[parent["type"]]
        for child_id in parent.get("children") or []:
            child = components.get(child_id)
            if child is None:
                problems.append(f"{parent_id} has unknown child {child_id}.")
            elif child["type"] not in accepted:
                problems.append(f"{parent_id} ({parent['type']}) does not accept a {child['type']} child "
                                f"({child_id}).")
            elif child_id in parent_of:
                problems.append(f"{child_id} has more than one parent ({parent_of[child_id]}, {parent_id}).")
            else:
                parent_of[child_id] = parent_id
    if ROOT_ID in parent_of:
        problems.append(f"{ROOT_ID} cannot have a parent.")
    return problems


def _find_cycle(components: dict[str, dict[str, Any]]) -> str | None:
    """A component in a cycle of `children` edges (iterative depth-first walk), or None."""
    state: dict[str, int] = {}  # 1: on the current path; 2: done
    for start in components:
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            component_id, leaving = stack.pop()
            if leaving:
                state[component_id] = 2
            elif state.get(component_id) == 1:
                return component_id
            elif component_id in components and state.get(component_id) != 2:
                state[component_id] = 1
                stack.append((component_id, True))
                stack.extend((child, False) for child in reversed(components[component_id].get("children") or []))
    return None


def _walk(components: dict[str, dict[str, Any]], check_parents: bool) -> tuple[set[str], list[str]]:
    """Components reachable from the root, with the nesting depth and `parents` problems found on the way."""
    problems: list[str] = []
    reachable: set[str] = set()
    stack: list[tuple[str, int, list[str]]] = [(ROOT_ID, ROOT_DEPTH, [])]
    while stack:
        component_id, depth, ancestors = stack.pop()
        component = components[component_id]
        reachable.add(component_id)
        # Missing parents are rebuilt by the frontend (hydrate.ts, updateComponentParentsList).
        stored_parents = component.get("parents", ancestors)
        if check_parents and component_id != ROOT_ID and stored_parents != ancestors:
            problems.append(f"{component_id}: parents {stored_parents} differ from the path {ancestors}.")
        child_depth = depth if component["type"] in DEPTH_TRANSPARENT_TYPES else depth + 1
        for child_id in reversed(component.get("children") or []):
            child = components.get(child_id)
            if child is None or child["type"] not in PARENT_MAX_DEPTH[component["type"]]:
                continue  # reported by _edge_problems
            if depth > PARENT_MAX_DEPTH[component["type"]][child["type"]]:
                problems.append(f"{child_id} ({child['type']}) is nested too deeply under {component_id}.")
            stack.append((child_id, child_depth, [*ancestors, component_id]))
    return reachable, problems


def _unreachable_problems(components: dict[str, dict[str, Any]], reachable: set[str]) -> list[str]:
    """Components outside the tree, except the title header and the empty grid kept beside top-level tabs."""
    root_children = components[ROOT_ID].get("children") or []
    top_level_tabs = bool(root_children) and components.get(root_children[0], {}).get("type") == "TABS"
    problems = []
    for component_id, component in components.items():
        if component_id in reachable or (component_id == HEADER_ID and component["type"] == "HEADER"):
            continue
        if component_id == GRID_ID and top_level_tabs and not component.get("children"):
            continue
        problems.append(f"{component_id} is not reachable from {ROOT_ID}.")
    return problems

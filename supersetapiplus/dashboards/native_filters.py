"""Native filters of a dashboard (`json_metadata.native_filter_configuration`).

Items are kept as the plain dicts Superset stores. The builders produce the same structure the dashboard
editor saves (``FiltersConfigModal/utils.ts::createHandleSave``, Superset 6.1.0); the scope fields
``chartsInScope``/``tabsInScope`` are derived from the layout as ``nativeFilters/utils.ts`` does.
"""
from __future__ import annotations

from dataclasses import dataclass

import shortuuid

from supersetapiplus.base.enum_str import StringEnum

NATIVE_FILTER_PREFIX = "NATIVE_FILTER-"
NATIVE_FILTER_DIVIDER_PREFIX = "NATIVE_FILTER_DIVIDER-"
DASHBOARD_ROOT_ID = "ROOT_ID"

# Defaults of the select filter form (filter_select controlValues) in the editor.
SELECT_CONTROL_VALUES = {
    "enableEmptyFilter": False,
    "defaultToFirstItem": False,
    "multiSelect": True,
    "searchAllOptions": False,
    "inverseSelection": False,
}


class NativeFilterType(StringEnum):
    """`NativeFilterType` in `@superset-ui/core` (query/types/Dashboard.ts)."""
    NATIVE_FILTER = "NATIVE_FILTER"
    DIVIDER = "DIVIDER"


class FilterType(StringEnum):
    """`filterType` of the filter plugins registered in `src/filters/components` (Superset 6.1.0)."""
    SELECT = "filter_select"
    RANGE = "filter_range"
    TIME = "filter_time"
    TIME_COLUMN = "filter_timecolumn"
    TIME_GRAIN = "filter_timegrain"


@dataclass(frozen=True)
class NativeFilterItem:
    """Handle to an item of `native_filter_configuration`; pass filters as ``parent`` of other filters."""
    config: dict

    @property
    def id(self) -> str:
        return self.config["id"]


def new_id(prefix: str) -> str:
    return f"{prefix}{shortuuid.ShortUUID().random(length=21)}"


def root_scope() -> dict:
    return {"rootPath": [DASHBOARD_ROOT_ID], "excluded": []}


def divider_config(title: str, description: str = "", id: str | None = None) -> dict:
    return {
        "id": id or new_id(NATIVE_FILTER_DIVIDER_PREFIX),
        "type": str(NativeFilterType.DIVIDER),
        "scope": root_scope(),
        "title": title,
        "description": description,
    }


def dataset_target(dataset, column: str | None) -> dict:
    """Filter target. Through the REST API Superset expects ``datasetId``; a ``str`` is taken as the
    dataset uuid (``datasetUuid``), which is the form used by dashboard import/export bundles.

    Without a dataset (e.g. a time range filter) the target is ``{}``, and a column needs a dataset, as in
    the filter editor (FiltersConfigModal createHandleSave, Superset 6.1.0)."""
    target: dict = {}
    if dataset is None:
        if column:
            raise ValueError("a filter column needs the dataset it belongs to.")
        return target
    if isinstance(dataset, str):
        target["datasetUuid"] = dataset
    elif isinstance(dataset, int):
        target["datasetId"] = dataset
    elif getattr(dataset, "id", None):
        target["datasetId"] = dataset.id
    else:
        raise TypeError("dataset must be a saved Dataset, a dataset id or a dataset uuid.")
    if column:
        target["column"] = {"name": column}
    return target


def chart_scope(charts_in_scope, layout_chart_ids) -> dict:
    """Scope covering only `charts_in_scope`: the dashboard root minus every other chart of the layout."""
    return {"rootPath": [DASHBOARD_ROOT_ID],
            "excluded": [chart_id for chart_id in layout_chart_ids if chart_id not in set(charts_in_scope)]}


def filter_config(name: str, dataset, column: str | None, parents: list[NativeFilterItem | str] | None = None,
                  filter_type: FilterType | str = FilterType.SELECT, adhoc_filters: list | None = None,
                  description: str = "", id: str | None = None, **control_values) -> dict:
    """Native filter as saved by the editor. Extra keyword arguments go to ``controlValues``, except the
    optional top-level keys ``time_range``, ``granularity_sqla``, ``sortMetric`` and ``defaultDataMask``."""
    top_level = {key: control_values.pop(key) for key in ("time_range", "granularity_sqla", "sortMetric")
                 if key in control_values}
    default_data_mask = control_values.pop("defaultDataMask", None) or {
        "extraFormData": {}, "filterState": {}, "ownState": {}}
    controls = dict(SELECT_CONTROL_VALUES) if str(filter_type) == str(FilterType.SELECT) else {}
    controls.update(control_values)
    config = {
        "id": id or new_id(NATIVE_FILTER_PREFIX),
        "adhoc_filters": list(adhoc_filters or []),
        "controlValues": controls,
        "name": name,
        "filterType": str(filter_type),
        "targets": [dataset_target(dataset, column)],
        "defaultDataMask": default_data_mask,
        "cascadeParentIds": [p.id if isinstance(p, NativeFilterItem) else str(p) for p in parents or []],
        "scope": root_scope(),
        "type": str(NativeFilterType.NATIVE_FILTER),
        "description": description.strip(),
    }
    config.update(top_level)
    return config

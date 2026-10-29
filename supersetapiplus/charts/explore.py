"""Explore's normalization of the stored params before buildQuery (Superset 6.1.0): params → form_data.

A chart saved in Superset is shown, and its ``query_context`` saved, by Explore, which does not build the query from
the params as stored. It first turns them into the form_data of the chart's controls:

1. the backend: ``Slice.form_data`` (superset/models/slice.py) applies ``update_time_range`` (superset/legacy.py),
   legacy ``since``/``until`` become ``time_range``; the Explore endpoint (superset/commands/explore/get.py) applies
   ``merge_extra_filters`` (superset/utils/core.py), which gives the stored ``time_range`` to the TEMPORAL_RANGE
   filters of a chart without ``granularity_sqla``;
2. ``hydrateExplore`` (src/explore/actions/hydrateExplore.ts): ``time_range`` defaults to "No filter", and a legacy
   time column with ``include_time`` becomes the first dimension;
3. each control of the viz_type takes its value (``getAllControlsState``, superset-frontend
   src/explore/controlUtils/getControlState.ts): the ``initialValue`` of the control (migrations such as the x axis
   from ``granularity_sqla``, the default time filter), else the stored value, else the control ``default`` when the
   stored one is null or absent;
4. the form_data holds only the controls (``getFormDataFromControls``): stored keys that are not controls of the
   viz_type are left out, and so are the controls hidden by their ``visibility`` (``StashFormDataContainer``).

:func:`explore_form_data` applies these steps to the params, so the library builds the query Explore builds. The
controls of each viz_type among the keys buildQuery reads (:data:`QUERY_CONTROLS`) are captured from Explore by
bin/scripts/extract_ui_controls.py (``tests/fixtures/ui_controls_<version>.json``); the defaults are those of the
chart models, which are the UI defaults (tests/unit/test_ui_defaults.py). Values Explore takes from the dataset (its
temporal columns) need :class:`DatasetTime`; without it those steps keep the stored values.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

NO_TIME_RANGE = "No filter"
# Suffix of the keys of the second query of the mixed chart. The form_data Explore sends with the queries leaves them
# out (the second query is built from them), so the probe of the controls cannot see them: they are kept as stored.
MIXED_SUFFIX = "_b"
# Controls whose value comes from an ``initialValue`` and that have no ``default`` (time_grain_sqla: P1D only for a
# new chart, sharedControls.tsx), or whose default the UI takes from the dataset: not filled from the model defaults.
INITIAL_VALUE_ONLY = frozenset(("time_grain_sqla", "x_axis", "adhoc_filters", "adhoc_filters_b",
                                "temporal_columns_lookup", "granularity_sqla", "columns", "datasource", "viz_type"))
# Control panels with the hidden ``temporal_columns_lookup`` control, recomputed from the dataset (sharedControls.tsx).
TEMPORAL_LOOKUP_VIZ_TYPES = frozenset(("table", "box_plot", "pivot_table_v2"))
# Controls whose ``time_grain_sqla`` is shown when a column of these controls is temporal (controlPanel.tsx of each
# plugin); the other viz types with an x axis use displayTimeRelatedControls (the x axis is temporal).
TIME_GRAIN_SHOWN_BY = {"table": ("groupby",), "box_plot": ("columns",), "pivot_table_v2": ("groupbyColumns", "groupbyRows")}

# Generated from tests/fixtures/ui_controls_6.1.0.json (bin/scripts/extract_ui_controls.py); checked by
# tests/unit/test_explore_form_data.py.
PROBED_KEYS: frozenset[str] = frozenset((
    "adhoc_filters", "aggregation", "all_columns", "annotation_layers", "bins", "column", "columns",
    "comparison_type", "contributionMode", "cumulative", "entity", "forecastEnabled", "forecastInterval",
    "forecastPeriods", "forecastSeasonalityDaily", "forecastSeasonalityWeekly", "forecastSeasonalityYearly",
    "granularity", "granularity_sqla", "group_others_when_limit_reached", "groupby", "groupbyColumns",
    "groupbyRows", "limit", "metric", "metric_2", "metrics", "min_periods", "normalize", "normalize_across",
    "order_by_cols", "order_desc", "percent_metric_calculation", "percent_metrics", "query_mode",
    "resample_method", "resample_rule", "rolling_periods", "rolling_type", "row_limit", "row_offset",
    "secondary_metric", "series", "series_columns", "series_limit", "series_limit_metric", "server_page_length",
    "server_pagination", "show_empty_columns", "show_totals", "size", "sort_by_metric", "sort_x_axis",
    "sort_y_axis", "start_date_offset", "time_compare", "time_grain_sqla", "time_range",
    "timeseries_limit_metric", "truncate_metric", "whiskerOptions", "x", "x_axis", "x_axis_sort",
    "x_axis_sort_asc", "y",
))
# viz_type -> the keys of PROBED_KEYS that are controls of its control panel.
QUERY_CONTROLS: dict[str, frozenset[str]] = {
    "big_number": frozenset((
        "adhoc_filters", "aggregation", "metric", "min_periods", "resample_method", "resample_rule",
        "rolling_periods", "rolling_type", "time_grain_sqla", "x_axis",
    )),
    "big_number_total": frozenset((
        "adhoc_filters", "metric",
    )),
    "box_plot": frozenset((
        "adhoc_filters", "columns", "groupby", "metrics", "row_limit", "series_limit", "series_limit_metric",
        "time_grain_sqla", "whiskerOptions",
    )),
    "bubble_v2": frozenset((
        "adhoc_filters", "entity", "row_limit", "series", "size", "x", "y",
    )),
    "cal_heatmap": frozenset((
        "adhoc_filters", "granularity_sqla", "metrics", "time_range",
    )),
    "echarts_area": frozenset((
        "adhoc_filters", "annotation_layers", "comparison_type", "contributionMode", "forecastEnabled",
        "forecastInterval", "forecastPeriods", "forecastSeasonalityDaily", "forecastSeasonalityWeekly",
        "forecastSeasonalityYearly", "group_others_when_limit_reached", "groupby", "limit", "metrics",
        "min_periods", "order_desc", "resample_method", "resample_rule", "rolling_periods", "rolling_type",
        "row_limit", "show_empty_columns", "time_compare", "time_grain_sqla", "timeseries_limit_metric",
        "truncate_metric", "x_axis", "x_axis_sort", "x_axis_sort_asc",
    )),
    "echarts_timeseries_bar": frozenset((
        "adhoc_filters", "annotation_layers", "comparison_type", "contributionMode", "forecastEnabled",
        "forecastInterval", "forecastPeriods", "forecastSeasonalityDaily", "forecastSeasonalityWeekly",
        "forecastSeasonalityYearly", "group_others_when_limit_reached", "groupby", "limit", "metrics",
        "min_periods", "order_desc", "resample_method", "resample_rule", "rolling_periods", "rolling_type",
        "row_limit", "show_empty_columns", "time_compare", "time_grain_sqla", "timeseries_limit_metric",
        "truncate_metric", "x_axis", "x_axis_sort", "x_axis_sort_asc",
    )),
    "echarts_timeseries_line": frozenset((
        "adhoc_filters", "annotation_layers", "comparison_type", "contributionMode", "forecastEnabled",
        "forecastInterval", "forecastPeriods", "forecastSeasonalityDaily", "forecastSeasonalityWeekly",
        "forecastSeasonalityYearly", "group_others_when_limit_reached", "groupby", "limit", "metrics",
        "min_periods", "order_desc", "resample_method", "resample_rule", "rolling_periods", "rolling_type",
        "row_limit", "show_empty_columns", "time_compare", "time_grain_sqla", "timeseries_limit_metric",
        "truncate_metric", "x_axis", "x_axis_sort", "x_axis_sort_asc",
    )),
    "funnel": frozenset((
        "adhoc_filters", "groupby", "metric", "row_limit", "sort_by_metric",
    )),
    "gauge_chart": frozenset((
        "adhoc_filters", "groupby", "metric", "row_limit", "sort_by_metric",
    )),
    "heatmap_v2": frozenset((
        "adhoc_filters", "groupby", "metric", "normalize_across", "row_limit", "sort_x_axis", "sort_y_axis",
        "time_grain_sqla", "x_axis",
    )),
    "histogram_v2": frozenset((
        "adhoc_filters", "bins", "column", "cumulative", "groupby", "normalize", "row_limit",
    )),
    "mixed_timeseries": frozenset((
        "adhoc_filters", "annotation_layers", "comparison_type", "groupby", "limit", "metrics", "min_periods",
        "order_desc", "resample_method", "resample_rule", "rolling_periods", "rolling_type", "row_limit",
        "time_compare", "time_grain_sqla", "timeseries_limit_metric", "truncate_metric", "x_axis",
    )),
    "pie": frozenset((
        "adhoc_filters", "groupby", "metric", "row_limit", "sort_by_metric",
    )),
    "pivot_table_v2": frozenset((
        "adhoc_filters", "groupbyColumns", "groupbyRows", "metrics", "order_desc", "row_limit", "series_limit",
        "series_limit_metric", "time_grain_sqla",
    )),
    "sunburst_v2": frozenset((
        "adhoc_filters", "columns", "metric", "row_limit", "secondary_metric", "sort_by_metric",
    )),
    "table": frozenset((
        "adhoc_filters", "all_columns", "comparison_type", "groupby", "metrics", "order_by_cols", "order_desc",
        "percent_metric_calculation", "percent_metrics", "query_mode", "row_limit", "server_page_length",
        "server_pagination", "show_totals", "start_date_offset", "time_compare", "time_grain_sqla",
        "timeseries_limit_metric",
    )),
    "treemap_v2": frozenset((
        "adhoc_filters", "groupby", "metric", "row_limit", "sort_by_metric",
    )),
    "word_cloud": frozenset((
        "adhoc_filters", "metric", "row_limit", "series", "sort_by_metric",
    )),
}


@dataclass(frozen=True)
class DatasetTime:
    """The temporal columns of the chart's dataset (``is_dttm``) and its main one (``main_dttm_col``)."""
    columns: tuple[str, ...] = ()
    main: str | None = None

    @property
    def default(self) -> str | None:
        """``getTemporalColumns(...).defaultTemporalColumn``: the main temporal column, else the first one."""
        return self.main or next(iter(self.columns), None)


def update_time_range(form_data: dict[str, Any]) -> None:
    """superset/legacy.py ``update_time_range``: legacy ``since``/``until`` become ``time_range``."""
    if "since" in form_data or "until" in form_data:
        since = form_data.pop("since", "") or ""
        until = form_data.pop("until", "") or ""
        form_data["time_range"] = f"{since} : {until}"
    column = form_data.get("granularity_sqla")
    if column and any(isinstance(f, dict) and f.get("subject") == column and f.get("comparator") == NO_TIME_RANGE
                      for f in form_data.get("adhoc_filters") or []):
        form_data.setdefault("time_range", NO_TIME_RANGE)


def merge_time_range(form_data: dict[str, Any]) -> None:
    """The time part of ``merge_extra_form_data`` (superset/utils/core.py) without dashboard extras: the stored
    ``time_range`` becomes the comparator of the TEMPORAL_RANGE filters when the chart has no ``granularity_sqla``."""
    time_range = form_data.get("time_range")
    if not time_range or form_data.get("granularity_sqla"):
        return
    for adhoc_filter in form_data.get("adhoc_filters") or []:
        if isinstance(adhoc_filter, dict) and adhoc_filter.get("operator") == "TEMPORAL_RANGE":
            adhoc_filter["comparator"] = time_range


def hydrate(form_data: dict[str, Any]) -> None:
    """``hydrateExplore`` before the controls: the default time range, and ``include_time`` with a legacy time
    column moves the column to the dimensions."""
    if not form_data.get("time_range"):
        form_data["time_range"] = NO_TIME_RANGE
    column = form_data.get("granularity_sqla")
    groupby = form_data.get("groupby")
    if form_data.get("include_time") and column and not any(
            _label(item) == _label(column) for item in _as_list(groupby)):
        form_data["groupby"] = [column, *_as_list(groupby)]
        form_data["granularity_sqla"] = None


def _label(column: Any) -> Any:
    """``getColumnLabel``: a physical column is its name, an adhoc one its label or SQL."""
    if isinstance(column, dict):
        return column.get("label") or column.get("sqlExpression")
    return column


def explore_form_data(form_data: Mapping[str, Any], defaults: Mapping[str, Any],
                      dataset: DatasetTime | None = None) -> dict[str, Any]:
    """The form_data Explore builds the query from, for the stored `form_data` (params) of a chart.

    `defaults` are the control defaults of the viz_type. A viz_type without captured controls only gets the
    backend step (``update_time_range``).
    """
    result = copy.deepcopy(dict(form_data))
    update_time_range(result)
    merge_time_range(result)
    viz_type = str(result.get("viz_type"))
    controls = QUERY_CONTROLS.get(viz_type)
    if controls is None:
        return result
    hydrate(result)
    _initial_values(result, viz_type, controls, dataset)
    for key, value in defaults.items():
        if key not in INITIAL_VALUE_ONLY and _is_control(key, controls) and result.get(key) is None \
                and value is not None:
            result[key] = copy.deepcopy(value)
    for key in [key for key in result if not _is_control(key, controls)]:
        del result[key]
    _hide(result, viz_type, dataset)
    return result


def _is_control(key: str, controls: frozenset[str]) -> bool:
    """Keys outside PROBED_KEYS (display options, request keys) are not decided here and are kept."""
    return key not in PROBED_KEYS or key in controls


def _initial_values(form_data: dict[str, Any], viz_type: str, controls: frozenset[str],
                    dataset: DatasetTime | None) -> None:
    """The ``initialValue`` of the controls that migrate legacy params or take a value from the dataset."""
    if dataset is not None and viz_type in TEMPORAL_LOOKUP_VIZ_TYPES:
        form_data["temporal_columns_lookup"] = dict.fromkeys(dataset.columns, True)
    # xAxisMixin (shared-controls/mixins.tsx): the legacy time column becomes the x axis.
    if "x_axis" in controls and form_data.get("granularity_sqla") and not form_data.get("x_axis"):
        form_data["x_axis"] = form_data["granularity_sqla"]
    # Box plot "Distribute across" (BoxPlot/controlPanel.ts): the dataset's temporal column when empty.
    if viz_type == "box_plot" and dataset is not None and dataset.default and not form_data.get("columns"):
        form_data["columns"] = [dataset.default]
    if "time_range" in controls:  # legacy charts keep their time range control
        return
    suffixes = ("", MIXED_SUFFIX) if viz_type == "mixed_timeseries" else ("",)
    for key in (f"adhoc_filters{suffix}" for suffix in suffixes):
        time_filter = _initial_time_filter(form_data, form_data.get(key), dataset)
        if time_filter is not None:
            form_data[key] = [*(form_data.get(key) or []), time_filter]


def _initial_time_filter(form_data: dict[str, Any], filters: Any,
                         dataset: DatasetTime | None) -> dict[str, Any] | None:
    """datePickerInAdhocFilterMixin (mixins.tsx): the TEMPORAL_RANGE filter a dashboard time range applies to,
    from the legacy time column and range, else on the dataset's default temporal column."""
    if any(isinstance(f, dict) and f.get("operator") == "TEMPORAL_RANGE" for f in filters or []):
        return None
    if form_data.get("granularity_sqla") and form_data.get("time_range"):
        subject, comparator = form_data["granularity_sqla"], form_data["time_range"]
    elif dataset is not None and dataset.default:
        subject, comparator = dataset.default, NO_TIME_RANGE
    else:
        return None
    return {"clause": "WHERE", "subject": subject, "operator": "TEMPORAL_RANGE", "comparator": comparator,
            "expressionType": "SIMPLE"}


def _hide(form_data: dict[str, Any], viz_type: str, dataset: DatasetTime | None) -> None:
    """Controls left out of the form_data while their ``visibility`` hides them."""
    if "server_page_length" in form_data and not form_data.get("server_pagination"):
        del form_data["server_page_length"]
    if "time_grain_sqla" in form_data and _time_grain_hidden(form_data, viz_type, dataset):
        del form_data["time_grain_sqla"]


def _time_grain_hidden(form_data: dict[str, Any], viz_type: str, dataset: DatasetTime | None) -> bool:
    """Whether the time grain is hidden: no temporal column where the plugin looks for one. Without the dataset or
    a stored ``temporal_columns_lookup`` the library cannot tell, and keeps it."""
    lookup = form_data.get("temporal_columns_lookup")
    if dataset is not None:
        temporal = set(dataset.columns)
    elif isinstance(lookup, dict):
        temporal = {column for column, is_temporal in lookup.items() if is_temporal}
    else:
        return False
    shown_by = TIME_GRAIN_SHOWN_BY.get(viz_type)
    if shown_by is None:  # displayTimeRelatedControls: shown without an x axis, or with a temporal one
        selected = [form_data["x_axis"]] if form_data.get("x_axis") else []
        if not selected:
            return False
    else:
        selected = [column for key in shown_by for column in _as_list(form_data.get(key))]
    return not any(isinstance(column, dict) or column in temporal for column in selected)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]

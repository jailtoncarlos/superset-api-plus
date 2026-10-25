"""Port of the Superset frontend `buildQuery` (Superset 6.1.0): chart `form_data` (params) → `query_context`.

In the Superset UI the `query_context` saved with a chart is not edited by the user: each plugin derives it
from the form data with its `buildQuery`. This module mirrors that code so charts built by the library carry
the same `query_context` the UI would save. Sources (superset-frontend, tag 6.1.0):

- ``packages/superset-ui-core/src/query``: ``buildQueryContext``, ``buildQueryObject``, ``extractQueryFields``,
  ``extractExtras``, ``processFilters``, ``convertFilter``, ``normalizeOrderBy``, ``normalizeTimeColumn``,
  ``getXAxis``, ``getColumnLabel``, ``getMetricLabel``;
- ``packages/superset-ui-chart-controls/src/operators``: the post-processing operators;
- the ``buildQuery.ts`` of each plugin listed in :data:`BUILD_QUERY`.

JavaScript ``undefined`` is represented by :data:`UNSET`; keys holding it are dropped from the result, as
``JSON.stringify`` does. Native and cross filter overrides (``extra_form_data`` other than ``filters`` and
``adhoc_filters``) are applied by the dashboard at run time and are not part of the saved query context.
"""
from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable
from typing import Any

UNSET = type("Unset", (), {"__repr__": lambda self: "UNSET", "__bool__": lambda self: False})()

DTTM_ALIAS = "__timestamp"
TIME_COMPARISON_SEPARATOR = "__"
COMPARISON_TYPES = ("values", "difference", "percentage", "ratio")
QUERY_MODE_AGGREGATE = "aggregate"
QUERY_MODE_RAW = "raw"

# Form data keys that buildQueryObject reads explicitly (not scanned by extractQueryFields).
_BASE_KEYS = (
    "annotation_layers", "extra_form_data", "time_range", "since", "until", "row_limit", "row_offset",
    "order_desc", "limit", "timeseries_limit_metric", "granularity", "url_params", "custom_params",
    "series_columns", "series_limit", "series_limit_metric", "group_others_when_limit_reached",
)
_QUERY_FIELD_ALIASES = {
    "metric": "metrics", "metric_2": "metrics", "secondary_metric": "metrics", "x": "metrics", "y": "metrics",
    "size": "metrics", "all_columns": "columns", "series": "groupby", "order_by_cols": "orderby",
}
_RESERVED_EXTRA_FILTER_COLUMNS = {
    "__time_range": "time_range", "__time_col": "granularity_sqla", "__time_grain": "time_grain_sqla",
    "__granularity": "granularity", "__time_compare": "time_compare",
}


# --- helpers from @superset-ui/core ----------------------------------------------------------------

def ensure_list(value: Any) -> list[Any]:
    if value is None or value is UNSET:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def defined(value: Any) -> bool:
    return value is not None and value is not UNSET


def is_empty(value: Any) -> bool:
    """lodash ``isEmpty``: empty collections, and anything that is not a non-empty collection or string."""
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) == 0
    return True


def is_physical_column(column: Any) -> bool:
    return isinstance(column, str)


def is_adhoc_column(column: Any) -> bool:
    return (isinstance(column, dict) and "sqlExpression" in column and "label" in column
            and column.get("expressionType", "SQL") == "SQL")


def is_query_form_column(column: Any) -> bool:
    return is_physical_column(column) or is_adhoc_column(column)


def is_query_form_metric(metric: Any) -> bool:
    return isinstance(metric, str) or (isinstance(metric, dict) and metric.get("expressionType") in ("SIMPLE", "SQL"))


def column_label(column: Any) -> str | None:
    if isinstance(column, str):
        return column
    label: str | None = column.get("label") or column.get("sqlExpression")
    return label


def metric_label(metric: Any) -> str | None:
    if isinstance(metric, str):
        return metric
    if metric.get("label"):
        return str(metric["label"])
    if metric.get("expressionType") == "SIMPLE":
        column = metric.get("column") or {}
        return f"{metric.get('aggregate')}({column.get('columnName') or column.get('column_name')})"
    expression: str | None = metric.get("sqlExpression")
    return expression


def remove_duplicates(items: list[Any], key: Callable[..., Any] = lambda item: item) -> list[Any]:
    seen, result = set(), []
    for item in items:
        identity = key(item)
        if identity not in seen:
            seen.add(identity)
            result.append(item)
    return result


def js_number(value: Any) -> Any:
    """``Number(value)``; NaN for values that are not numbers."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).strip()) if str(value).strip() else 0.0
    except ValueError:
        return math.nan
    return int(number) if number.is_integer() else number


def js_int(value: Any, default: float) -> float:
    """``ensureIsInt``: ``parseInt`` with a default for values that are not integers (NaN for plain parseInt)."""
    match = re.match(r"\s*([+-]?\d+)", str(value)) if defined(value) else None
    return int(match.group(1)) if match else default


_JS_FLOAT = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")


def js_float(value: Any) -> float:
    """``parseFloat``: the leading number of the text; NaN when there is none."""
    match = _JS_FLOAT.match(str(value)) if defined(value) else None
    return float(match.group(1)) if match else math.nan


def drop_unset(value: Any) -> Any:
    """Removes ``UNSET`` keys recursively, as ``JSON.stringify`` drops ``undefined`` (and writes NaN as null)."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {key: drop_unset(item) for key, item in value.items() if item is not UNSET}
    if isinstance(value, list):
        return [None if item is UNSET else drop_unset(item) for item in value]
    return value


# --- x axis -----------------------------------------------------------------------------------------

def is_x_axis_set(form_data: dict[str, Any]) -> bool:
    return is_query_form_column(form_data.get("x_axis"))


def x_axis_column(form_data: dict[str, Any]) -> Any:
    if not (form_data.get("granularity_sqla") or form_data.get("x_axis")):
        return UNSET
    return form_data["x_axis"] if is_x_axis_set(form_data) else DTTM_ALIAS


def x_axis_label(form_data: dict[str, Any]) -> Any:
    column = x_axis_column(form_data)
    return column_label(column) if column is not UNSET else UNSET


def normalize_time_column(form_data: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    x_axis = form_data.get("x_axis")
    columns = query.get("columns")
    if not isinstance(columns, list):
        return query
    index = next((i for i, col in enumerate(columns) if _is_x_axis(col, x_axis)), -1)
    if index < 0:
        return query
    grain = (query.get("extras") or {}).get("time_grain_sqla", UNSET)
    mutated = list(columns)
    if is_adhoc_column(columns[index]):
        mutated[index] = {"timeGrain": grain, "columnType": "BASE_AXIS", **columns[index]}
    else:
        mutated[index] = {"timeGrain": grain, "columnType": "BASE_AXIS", "sqlExpression": x_axis, "label": x_axis,
                          "expressionType": "SQL", "isColumnReference": True}
    result = {key: value for key, value in query.items() if key != "is_timeseries"}
    result["columns"] = mutated
    return result


def _is_x_axis(column: Any, x_axis: Any) -> bool:
    if is_physical_column(column) and is_physical_column(x_axis):
        return bool(column == x_axis)
    return (is_adhoc_column(column) and is_adhoc_column(x_axis)
            and bool(column["sqlExpression"] == x_axis["sqlExpression"]))


# --- buildQueryObject -------------------------------------------------------------------------------

def extract_query_fields(residual: dict[str, Any]) -> dict[str, Any]:
    query_mode = residual.get("query_mode")
    collected: dict[str, list[Any]] = {"columns": [], "metrics": [], "orderby": []}
    for key, value in residual.items():
        if key == "query_mode" or value is None or value is UNSET:
            continue
        name = _QUERY_FIELD_ALIASES.get(key, key)
        if _ignored_in_mode(query_mode, name):
            continue
        name = "columns" if name == "groupby" else name
        if name in collected:
            collected[name].extend(ensure_list(value))
    orderby = [_parse_orderby(item) for item in collected["orderby"]]
    return {
        "columns": remove_duplicates([c for c in collected["columns"] if c != ""], _hashable(column_label)),
        "metrics": UNSET if query_mode == QUERY_MODE_RAW else remove_duplicates(collected["metrics"],
                                                                                 _hashable(metric_label)),
        "orderby": orderby if orderby else UNSET,
    }


def _ignored_in_mode(query_mode: Any, name: str) -> bool:
    if query_mode == QUERY_MODE_AGGREGATE:
        return name == "columns"
    return query_mode == QUERY_MODE_RAW and name in ("groupby", "metrics")


def _parse_orderby(item: Any) -> Any:
    if isinstance(item, str):
        import json
        return json.loads(item)
    return item


def _hashable(label: Callable[..., Any]) -> Callable[..., Any]:
    return lambda item: label(item) if label(item) is not None else id(item)


def extract_extras(form_data: dict[str, Any]) -> dict[str, Any]:
    extract: dict[str, Any] = {"filters": [], "extras": {}, "applied_time_extras": {}}
    for extra_filter in form_data.get("extra_filters") or []:
        query_field = _RESERVED_EXTRA_FILTER_COLUMNS.get(extra_filter.get("col"))
        if query_field:
            extract[query_field] = extra_filter.get("val")
            extract["applied_time_extras"][extra_filter["col"]] = extra_filter.get("val")
        else:
            extract["filters"].append(extra_filter)
    extract["extras"]["time_grain_sqla"] = extract.get("time_grain_sqla") or form_data.get("time_grain_sqla", UNSET)
    extract["granularity"] = (extract.get("granularity_sqla") or form_data.get("granularity")
                              or form_data.get("granularity_sqla", UNSET))
    extract.pop("granularity_sqla", None)
    extract.pop("time_grain_sqla", None)
    return extract


def convert_filter(adhoc_filter: dict[str, Any]) -> dict[str, Any]:
    clause = {"col": adhoc_filter.get("subject"), "op": adhoc_filter.get("operator")}
    if "comparator" in adhoc_filter:
        clause["val"] = adhoc_filter["comparator"]
    return clause


def process_filters(form_data: dict[str, Any]) -> dict[str, Any]:
    simple_where = form_data.get("filters") or []
    freeform_where = [form_data["where"]] if form_data.get("where") else []
    freeform_having = []
    for adhoc_filter in form_data.get("adhoc_filters") or []:
        clause = adhoc_filter.get("clause")
        if adhoc_filter.get("expressionType") == "SIMPLE":
            if clause == "WHERE":
                simple_where.append(convert_filter(adhoc_filter))
        elif clause == "WHERE":
            freeform_where.append(adhoc_filter.get("sqlExpression"))
        else:
            freeform_having.append(adhoc_filter.get("sqlExpression"))
    extras = form_data.get("extras") or {}
    extras["having"] = " AND ".join(_sanitize_clause(c) for c in freeform_having)
    extras["where"] = " AND ".join(_sanitize_clause(c) for c in freeform_where)
    return {"filters": simple_where, "extras": extras}


def _sanitize_clause(clause: str) -> str:
    return f"({clause}\n)" if "--" in clause else f"({clause})"


def build_query_object(form_data: dict[str, Any]) -> dict[str, Any]:
    residual = {key: value for key, value in form_data.items() if key not in _BASE_KEYS}
    extra_form_data = form_data.get("extra_form_data") or {}
    fields = extract_query_fields(residual)
    extras = extract_extras(form_data)
    filters = process_filters({
        **form_data, **extras,
        "filters": [*extras["filters"], *(extra_form_data.get("filters") or [])],
        "adhoc_filters": [*(form_data.get("adhoc_filters") or []), *(extra_form_data.get("adhoc_filters") or [])],
    })
    query = {
        "time_range": form_data.get("time_range") or UNSET,
        "since": form_data.get("since") or UNSET,
        "until": form_data.get("until") or UNSET,
        **extras, **filters, **fields,
        "annotation_layers": form_data.get("annotation_layers", []),
        "row_limit": _optional_number(form_data.get("row_limit")),
        "row_offset": _optional_number(form_data.get("row_offset")),
        "series_columns": form_data.get("series_columns", UNSET),
        "series_limit": _series_limit(form_data),
        "series_limit_metric": _series_limit_metric(form_data),
        "group_others_when_limit_reached": _coalesce(form_data.get("group_others_when_limit_reached"), False),
        "order_desc": form_data.get("order_desc", True),
        "url_params": form_data.get("url_params") or {},
        "custom_params": form_data.get("custom_params", {}),
    }
    return {**query, "custom_form_data": extra_form_data.get("custom_form_data", {})}


def _coalesce(value: Any, default: Any) -> Any:
    return value if defined(value) else default


def _optional_number(value: Any) -> Any:
    if not defined(value):
        return UNSET
    number = js_number(value)
    return UNSET if isinstance(number, float) and math.isnan(number) else number


def _series_limit(form_data: dict[str, Any]) -> Any:
    if defined(form_data.get("series_limit")):
        return form_data["series_limit"]
    return js_number(form_data["limit"]) if defined(form_data.get("limit")) else 0


def _series_limit_metric(form_data: dict[str, Any]) -> Any:
    metric = form_data.get("series_limit_metric")
    if is_query_form_metric(metric):
        return metric
    return _coalesce(form_data.get("timeseries_limit_metric"), UNSET)


def normalize_orderby(query: dict[str, Any]) -> dict[str, Any]:
    orderby = query.get("orderby")
    if isinstance(orderby, list) and orderby:
        clause = orderby[0]
        if (isinstance(clause, (list, tuple)) and len(clause) == 2 and not is_empty(clause[0])
                and isinstance(clause[1], bool)):
            return query
    clone = {key: value for key, value in query.items()
             if key not in ("series_limit_metric", "legacy_order_by", "order_desc", "orderby")}
    ascending = not query.get("order_desc")
    for candidate in (query.get("series_limit_metric"), query.get("legacy_order_by")):
        if defined(candidate) and not is_empty(candidate):
            return {**clone, "orderby": [[candidate, ascending]]}
    metrics = query.get("metrics")
    if isinstance(metrics, list) and metrics:
        return {**clone, "orderby": [[metrics[0], ascending]]}
    return clone


def build_query_context(form_data: dict[str, Any],
                        build: Callable[[dict[str, Any]], list[Any]] | None = None) -> dict[str, Any]:
    """``buildQueryContext``: the query context for `form_data`, with `build` as the plugin hook."""
    form_data = copy.deepcopy(form_data)
    queries = (build or (lambda base: [base]))(build_query_object(form_data))
    for query in queries:
        if isinstance(query.get("post_processing"), list):
            query["post_processing"] = [rule for rule in query["post_processing"] if rule]
    if is_x_axis_set(form_data):
        queries = [normalize_time_column(form_data, query) for query in queries]
    context: dict[str, Any] = drop_unset({
        "datasource": _datasource(form_data.get("datasource")),
        "force": form_data.get("force") or False,
        "queries": queries,
        "form_data": form_data,
        "result_format": form_data.get("result_format") or "json",
        "result_type": form_data.get("result_type") or "full",
    })
    return context


def _datasource(key: Any) -> dict[str, Any]:
    """``DatasourceKey("12__table").toObject()``."""
    if isinstance(key, dict):
        return {"id": key.get("id"), "type": key.get("type")}
    if not isinstance(key, str) or "__" not in key:
        return {"id": UNSET, "type": UNSET}
    pk, kind = key.split("__", 1)
    return {"id": int(pk) if pk.isdigit() else pk, "type": kind}


# --- post-processing operators (superset-ui-chart-controls) -----------------------------------------

def metric_offsets(form_data: dict[str, Any], query: dict[str, Any]) -> dict[str, str | None]:
    labels = [metric_label(m) for m in ensure_list(query.get("metrics"))]
    return {f"{label}{TIME_COMPARISON_SEPARATOR}{offset}": label
            for label in labels for offset in ensure_list(form_data.get("time_compare"))}


def is_time_comparison(form_data: dict[str, Any], query: dict[str, Any]) -> bool:
    return form_data.get("comparison_type") in COMPARISON_TYPES and bool(metric_offsets(form_data, query))


def extra_metrics(form_data: dict[str, Any]) -> list[Any]:
    limit_metric = next(iter(ensure_list(form_data.get("timeseries_limit_metric"))), None)
    sort = form_data.get("x_axis_sort")
    if (not ensure_list(form_data.get("groupby")) and limit_metric and metric_label(limit_metric) == sort
            and not any(metric_label(m) == sort for m in ensure_list(form_data.get("metrics")))):
        return [limit_metric]
    return []


def js_truthy(value: Any) -> bool:
    """JavaScript truthiness: empty lists and dicts are truthy."""
    if isinstance(value, (list, dict)):
        return True
    return defined(value) and bool(value) and not (isinstance(value, float) and math.isnan(value))


def _series_columns(query: dict[str, Any]) -> list[Any]:
    series = query.get("series_columns")
    return ensure_list(series if js_truthy(series) else query.get("columns"))


def pivot_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    labels = [metric_label(m) for m in [*ensure_list(query.get("metrics")), *extra_metrics(form_data)]]
    x_label = x_axis_label(form_data)
    if not x_label or not labels:
        return UNSET
    return {"operation": "pivot", "options": {
        "index": [x_label],
        "columns": [column_label(c) for c in _series_columns(query)],
        "aggregates": {label: {"operator": "mean"} for label in labels},
        "drop_missing_columns": not form_data.get("show_empty_columns"),
    }}


def time_compare_pivot_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    x_label = x_axis_label(form_data)
    if not (is_time_comparison(form_data, query) and x_label):
        return UNSET
    offsets = metric_offsets(form_data, query)
    return {"operation": "pivot", "options": {
        "index": [x_label],
        "columns": [column_label(c) for c in _series_columns(query)],
        "drop_missing_columns": not form_data.get("show_empty_columns"),
        "aggregates": {m: {"operator": "mean"} for m in [*dict.fromkeys(offsets.values()), *offsets]},
    }}


def resample_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    zero_fill = form_data.get("resample_method") == "zerofill"
    method = "asfreq" if zero_fill else form_data.get("resample_method")
    rule = form_data.get("resample_rule")
    if not (method and rule):
        return UNSET
    return {"operation": "resample", "options": {"method": method, "rule": rule, "fill_value": 0 if zero_fill else None}}


def rolling_window_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    if is_time_comparison(form_data, query):
        offsets = metric_offsets(form_data, query)
        columns = [*offsets.values(), *offsets]
    else:
        columns = [m if isinstance(m, str) else m.get("label", UNSET) for m in ensure_list(query.get("metrics"))]
    columns_map = {col: col for col in columns}
    rolling_type = form_data.get("rolling_type")
    if rolling_type == "cumsum":
        return {"operation": "cum", "options": {"operator": "sum", "columns": columns_map}}
    if rolling_type in ("sum", "mean", "std"):
        return {"operation": "rolling", "options": {
            "rolling_type": rolling_type, "window": js_int(form_data.get("rolling_periods"), 1),
            "min_periods": js_int(form_data.get("min_periods"), 0), "columns": columns_map}}
    return UNSET


def time_compare_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    comparison = form_data.get("comparison_type")
    if not is_time_comparison(form_data, query) or comparison == "values":
        return UNSET
    offsets = metric_offsets(form_data, query)
    return {"operation": "compare", "options": {
        "source_columns": list(offsets.values()), "compare_columns": list(offsets),
        "compare_type": comparison, "drop_original_columns": True}}


def rename_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    metrics = ensure_list(query.get("metrics"))
    offsets = ensure_list(form_data.get("time_compare"))
    comparing = is_time_comparison(form_data, query)
    truncate = defined(form_data.get("truncate_metric")) and bool(form_data.get("truncate_metric"))
    wanted = comparing or ((_series_columns(query) or len(offsets) > 1) and truncate)
    if not (metrics and x_axis_label(form_data) and wanted):
        return UNSET
    pairs = _time_comparison_renames(form_data, query, len(metrics)) if comparing else []
    comparison = form_data.get("comparison_type")
    if comparison not in ("difference", "percentage", "ratio") and len(metrics) == 1 and not pairs:
        pairs.append((metric_label(metrics[0]), None))
    if not pairs:
        return UNSET
    return {"operation": "rename", "options": {"columns": dict(pairs), "level": 0, "inplace": True}}


def _time_comparison_renames(form_data: dict[str, Any], query: dict[str, Any], metric_count: int) -> list[Any]:
    pairs = []
    comparison = form_data.get("comparison_type")
    for with_offset, metric in metric_offsets(form_data, query).items():
        offset = next((o for o in ensure_list(form_data.get("time_compare")) if o in with_offset), UNSET)
        source = with_offset if comparison == "values" else TIME_COMPARISON_SEPARATOR.join(
            [str(comparison), metric or "", with_offset])
        pairs.append((source, f"{metric}, {offset}" if metric_count > 1 else offset))
    return pairs


def contribution_operator(form_data: dict[str, Any], query: dict[str, Any], time_shifts: list[Any]) -> Any:
    if not form_data.get("contributionMode"):
        return UNSET
    return {"operation": "contribution", "options": {"orientation": form_data["contributionMode"],
                                                     "time_shifts": time_shifts}}


def sort_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    x_label = x_axis_label(form_data)
    labels = [label for label in [x_label, *(metric_label(m) for m in ensure_list(form_data.get("metrics"))),
                                  *(metric_label(m) for m in extra_metrics(form_data))] if label]
    sort, ascending = form_data.get("x_axis_sort"), form_data.get("x_axis_sort_asc")
    if not (defined(sort) and defined(ascending) and sort in labels and is_empty(form_data.get("groupby"))):
        return UNSET
    if sort == x_label:
        return {"operation": "sort", "options": {"is_sort_index": True, "ascending": ascending}}
    return {"operation": "sort", "options": {"by": sort, "ascending": ascending}}


def flatten_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    return {"operation": "flatten"}


def prophet_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    x_label = x_axis_label(form_data)
    if not (form_data.get("forecastEnabled") and x_label):
        return UNSET
    return {"operation": "prophet", "options": {
        "time_grain": form_data.get("time_grain_sqla", UNSET),
        "periods": js_int(form_data.get("forecastPeriods"), math.nan),
        "confidence_interval": js_float(form_data.get("forecastInterval")),
        "yearly_seasonality": form_data.get("forecastSeasonalityYearly", UNSET),
        "weekly_seasonality": form_data.get("forecastSeasonalityWeekly", UNSET),
        "daily_seasonality": form_data.get("forecastSeasonalityDaily", UNSET),
        "index": x_label,
    }}


_PERCENTILES = re.compile(r"(\d+)/(\d+) percentiles")


def boxplot_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    whiskers = form_data.get("whiskerOptions")
    if not whiskers:
        return UNSET
    percentiles, match = UNSET, _PERCENTILES.search(str(whiskers))
    if whiskers == "Tukey":
        whisker_type = "tukey"
    elif whiskers == "Min/max (no outliers)":
        whisker_type = "min/max"
    elif match:
        whisker_type, percentiles = "percentile", [int(match.group(1)), int(match.group(2))]
    else:
        raise ValueError(f"Unsupported whisker type: {whiskers}")
    return {"operation": "boxplot", "options": {
        "whisker_type": whisker_type, "percentiles": percentiles,
        "groupby": [column_label(c) for c in ensure_list(form_data.get("groupby"))],
        "metrics": [metric_label(m) for m in ensure_list(query.get("metrics"))],
    }}


# --- plugins ----------------------------------------------------------------------------------------

def _temporal_base_axis(column: Any, form_data: dict[str, Any], time_grain: Any) -> Any:
    if is_physical_column(column) and time_grain and (form_data.get("temporal_columns_lookup") or {}).get(column):
        return {"timeGrain": time_grain, "columnType": "BASE_AXIS", "sqlExpression": column, "label": column,
                "expressionType": "SQL"}
    return column


def build_pie(form_data: dict[str, Any]) -> dict[str, Any]:
    metric = form_data.get("metric")
    label = metric_label(metric)

    def build(base: dict[str, Any]) -> list[Any]:
        query = {**base, "post_processing": [{"operation": "contribution", "options": {
            "columns": [label], "rename_columns": [f"{label}__contribution"]}}]}
        if form_data.get("sort_by_metric"):
            query["orderby"] = [[metric, False]]
        return [query]

    return build_query_context(form_data, build)


def build_word_cloud(form_data: dict[str, Any]) -> dict[str, Any]:
    metric, series, row_limit = form_data.get("metric"), form_data.get("series"), form_data.get("row_limit")
    orderby = []
    if form_data.get("sort_by_metric") and metric:
        orderby.append([metric, False])
    if series:
        orderby.append([series, True])
    apply = defined(row_limit) and row_limit != 0 and bool(orderby)
    return build_query_context(form_data, lambda base: [{**base, "orderby": orderby} if apply else base])


def build_columns_orderby(columns: Any, ascending: bool = True) -> list[Any]:
    """``buildColumnsOrderBy`` (plugin-chart-echarts utils/orderby.ts): physical columns only."""
    return [[column, ascending] for column in ensure_list(columns) if isinstance(column, str) and column != ""]


def apply_orderby(orderby: list[Any], row_limit: Any) -> dict[str, Any]:
    """``applyOrderBy``: the orderby, unless there is no row limit or it is 0 (a non-numeric text applies)."""
    if not defined(row_limit) or not orderby:
        return {}
    parsed = js_number(row_limit) if isinstance(row_limit, str) else row_limit
    applies = (isinstance(parsed, float) and math.isnan(parsed)) or parsed != 0
    return {"orderby": orderby} if applies else {}


def build_treemap(form_data: dict[str, Any]) -> dict[str, Any]:
    metric = form_data.get("metric")
    orderby = [[metric, False]] if form_data.get("sort_by_metric") and metric else []
    orderby.extend(build_columns_orderby(form_data.get("groupby")))
    return build_query_context(form_data, lambda base: [{**base, **apply_orderby(orderby, form_data.get("row_limit"))}])


def build_pivot_table_v2(form_data: dict[str, Any]) -> dict[str, Any]:
    grain = (form_data.get("extra_form_data") or {}).get("time_grain_sqla") or form_data.get("time_grain_sqla")
    raw = [*ensure_list(form_data.get("groupbyColumns")), *ensure_list(form_data.get("groupbyRows"))]
    unique = [c for i, c in enumerate(raw) if not isinstance(c, str) or c not in raw[:i]]
    lookup = dict(form_data.get("temporal_columns_lookup") or {})
    if isinstance(form_data.get("granularity_sqla"), str):
        lookup[form_data["granularity_sqla"]] = True
    columns = [_temporal_base_axis(c, {"temporal_columns_lookup": lookup}, grain) for c in unique]

    def build(base: dict[str, Any]) -> list[Any]:
        limit_metric, metrics = base.get("series_limit_metric"), base.get("metrics")
        orderby = UNSET
        if limit_metric:
            orderby = [[limit_metric, not base.get("order_desc")]]
        elif isinstance(metrics, list) and metrics and metrics[0]:
            orderby = [[metrics[0], not base.get("order_desc")]]
        return [{**base, "orderby": orderby, "columns": columns}]

    return build_query_context(form_data, build)


def build_box_plot(form_data: dict[str, Any]) -> dict[str, Any]:
    columns = ensure_list(form_data.get("columns"))
    if not columns and form_data.get("granularity_sqla"):
        columns = [form_data["granularity_sqla"]]
    grain = form_data.get("time_grain_sqla")

    def build(base: dict[str, Any]) -> list[Any]:
        return [{**base,
                 "columns": [*(_temporal_base_axis(c, form_data, grain) for c in columns),
                             *ensure_list(form_data.get("groupby"))],
                 "series_columns": form_data.get("groupby", UNSET),
                 "post_processing": [boxplot_operator(form_data, base)]}]

    return build_query_context(form_data, build)


def _x_axis_and_groupby(form_data: dict[str, Any], groupby: Any) -> list[Any]:
    axis = ensure_list(x_axis_column(form_data)) if is_x_axis_set(form_data) else []
    return [*axis, *ensure_list(groupby)]


def _timeseries_pivot(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    if is_time_comparison(form_data, query):
        return time_compare_pivot_operator(form_data, query)
    return pivot_operator(form_data, query)


def build_timeseries(form_data: dict[str, Any]) -> dict[str, Any]:
    groupby = form_data.get("groupby", UNSET)

    def build(base: dict[str, Any]) -> list[Any]:
        offsets = form_data.get("time_compare", UNSET) if is_time_comparison(form_data, base) else []
        query = {**base,
                 "metrics": [*(base.get("metrics") or []), *extra_metrics(form_data)],
                 "columns": _x_axis_and_groupby(form_data, groupby),
                 "series_columns": groupby,
                 "orderby": normalize_orderby(base).get("orderby", UNSET),
                 "time_offsets": offsets}
        if not is_x_axis_set(form_data):
            query["is_timeseries"] = True
        query["post_processing"] = [
            _timeseries_pivot(form_data, base), resample_operator(form_data, base),
            rolling_window_operator(form_data, base), time_compare_operator(form_data, base),
            rename_operator(form_data, base), contribution_operator(form_data, base, offsets),
            sort_operator(form_data, base), flatten_operator(form_data, base), prophet_operator(form_data, base)]
        return [query]

    return build_query_context(form_data, build)


def retain_form_data_suffix(form_data: dict[str, Any], suffix: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in sorted(form_data.items(), key=lambda item: 0 if item[0].endswith(suffix) else 1):
        if key.endswith(suffix):
            result[key[:-len(suffix)]] = value
        elif key not in result:
            result[key] = value
    return result


def remove_form_data_suffix(form_data: dict[str, Any], suffix: str) -> dict[str, Any]:
    return {key: value for key, value in form_data.items() if not key.endswith(suffix)}


def build_mixed_timeseries(form_data: dict[str, Any]) -> dict[str, Any]:
    def builder(fd: dict[str, Any]) -> Callable[[dict[str, Any]], list[Any]]:
        def build(base: dict[str, Any]) -> list[Any]:
            query = {**base, "columns": _x_axis_and_groupby(form_data, fd.get("groupby")),
                     "series_columns": fd.get("groupby", UNSET)}
            if not is_x_axis_set(form_data):
                query["is_timeseries"] = True
            query["time_offsets"] = fd.get("time_compare", UNSET) if is_time_comparison(fd, query) else []
            query["post_processing"] = [
                _timeseries_pivot(fd, query), resample_operator(fd, query), rolling_window_operator(fd, query),
                time_compare_operator(fd, query), rename_operator(fd, query), flatten_operator(fd, query)]
            return [normalize_orderby(query)]
        return build

    first, second = (remove_form_data_suffix(form_data, "_b"), retain_form_data_suffix(form_data, "_b"))
    contexts = [build_query_context(fd, builder(fd)) for fd in (first, second)]
    return {**contexts[0], "queries": [*contexts[0]["queries"], *contexts[1]["queries"]]}


def table_query_mode(form_data: dict[str, Any]) -> str:
    mode = form_data.get("query_mode")
    if mode in (QUERY_MODE_AGGREGATE, QUERY_MODE_RAW):
        return str(mode)
    return QUERY_MODE_RAW if ensure_list(form_data.get("all_columns")) else QUERY_MODE_AGGREGATE


def _table_time_offsets(form_data: dict[str, Any], base: dict[str, Any]) -> list[Any]:
    shifts = ensure_list(form_data.get("time_compare"))
    offsets: list[Any] = []
    if is_time_comparison(form_data, base):
        offsets = [s for s in shifts if s not in ("custom", "inherit")]
        if "custom" in shifts:
            offsets.append(form_data.get("start_date_offset"))
        if "inherit" in shifts:
            offsets.append("inherit")
    extra_compare = (form_data.get("extra_form_data") or {}).get("time_compare")
    return [extra_compare] if extra_compare and extra_compare not in offsets else offsets


def _table_aggregate(form_data: dict[str, Any], base: dict[str, Any], offsets: list[Any]) -> dict[str, Any]:
    metrics = base.get("metrics") or []
    sort_metric = next(iter(ensure_list(form_data.get("timeseries_limit_metric"))), None)
    orderby = base.get("orderby") or []
    if sort_metric:
        orderby = [[sort_metric, not form_data.get("order_desc", False)]]
    elif metrics:
        orderby = [[metrics[0], False]]
    post_processing = []
    percent_metrics = ensure_list(form_data.get("percent_metrics"))
    if percent_metrics:
        labels = [metric_label(m) for m in percent_metrics]
        if is_time_comparison(form_data, base):
            labels = [name for label in labels for name in [label, *(f"{label}__{o}" for o in offsets)]]
        labels = remove_duplicates(labels)
        metrics = remove_duplicates([*metrics, *percent_metrics], _hashable(metric_label))
        post_processing.append({"operation": "contribution", "options": {
            "columns": labels, "rename_columns": [f"%{label}" for label in labels]}})
    if offsets:
        post_processing.append(time_compare_operator(form_data, base))
    return {"metrics": metrics, "orderby": orderby, "post_processing": post_processing,
            "columns": _table_columns(form_data, base.get("columns") or [])}


def _table_columns(form_data: dict[str, Any], columns: list[Any]) -> list[Any]:
    grain = (form_data.get("extra_form_data") or {}).get("time_grain_sqla") or form_data.get("time_grain_sqla")
    for index, column in enumerate(columns):
        temporal = _temporal_base_axis(column, form_data, grain)
        if temporal is not column:
            return [temporal, *columns[:index], *columns[index + 1:]]
    return columns


def _table_extra_queries(form_data: dict[str, Any], query: dict[str, Any], mode: str) -> list[Any]:
    extra = []
    percent_metrics = ensure_list(form_data.get("percent_metrics"))
    if form_data.get("percent_metric_calculation") == "all_records" and percent_metrics:
        extra.append({**query, "columns": [], "metrics": percent_metrics, "post_processing": [], "row_limit": 0,
                      "row_offset": 0, "orderby": [], "is_timeseries": False})
    if query.get("metrics") and form_data.get("show_totals") and mode == QUERY_MODE_AGGREGATE:
        extra.append({**query, "columns": [], "row_limit": 0, "row_offset": 0, "post_processing": [],
                      "order_desc": UNSET, "orderby": UNSET})
    return extra


def _is_download(form_data: dict[str, Any]) -> bool:
    result_format = form_data.get("result_format") or ""
    return result_format in ("csv", "xlsx") or (result_format == "json" and form_data.get("result_type") == "results")


def _table_paging(form_data: dict[str, Any]) -> dict[str, Any]:
    """Row window of the main query (no ownState: first page, as when the chart is saved)."""
    if _is_download(form_data):
        return {"row_limit": js_number(form_data.get("row_limit") or 0) or 0, "row_offset": 0}
    if form_data.get("server_pagination"):
        return {"row_limit": form_data.get("server_page_length", UNSET), "row_offset": 0}
    return {}


def build_table(form_data: dict[str, Any]) -> dict[str, Any]:
    mode = table_query_mode(form_data)
    query_form_data = {**form_data, "include_time": False} if mode == QUERY_MODE_RAW else form_data

    def build(base: dict[str, Any]) -> list[Any]:
        offsets = _table_time_offsets(form_data, base)
        parts = {"metrics": base.get("metrics", UNSET), "orderby": base.get("orderby") or [],
                 "post_processing": [], "columns": base.get("columns") or []}
        if mode == QUERY_MODE_AGGREGATE:
            parts = _table_aggregate(form_data, base, offsets)
        query = {**base, **parts, "extras": base.get("extras") or {}, "time_offsets": offsets,
                 **_table_paging(form_data)}
        extra = _table_extra_queries(form_data, query, mode)
        interactive = (form_data.get("extra_form_data") or {}).get("interactive_groupby")
        if interactive and query.get("columns"):
            query["columns"] = list(dict.fromkeys([*query["columns"], *interactive]))
        if form_data.get("server_pagination") and not _is_download(form_data):
            rowcount = {**query, "time_offsets": [], "row_limit": js_number(form_data.get("row_limit") or 0),
                        "row_offset": 0, "post_processing": [], "is_rowcount": True}
            return [query, rowcount, *extra]
        return [query, *extra]

    return build_query_context(query_form_data, build)


def build_sorted_by_metric(form_data: dict[str, Any]) -> dict[str, Any]:
    """Funnel, Gauge and Sunburst buildQuery: ordered by the metric when ``sort_by_metric``."""
    metric = form_data.get("metric", UNSET)
    orderby = {"orderby": [[metric, False]]} if form_data.get("sort_by_metric") else {}
    return build_query_context(form_data, lambda base: [{**base, **orderby}])


def build_big_number(form_data: dict[str, Any]) -> dict[str, Any]:
    """BigNumberWithTrendline buildQuery: the trendline, plus the raw value query when ``aggregation`` is raw."""
    time_column = ensure_list(x_axis_column(form_data)) if is_x_axis_set(form_data) else []

    def build(base: dict[str, Any]) -> list[Any]:
        trendline = {**base, "columns": list(time_column), **({} if time_column else {"is_timeseries": True}),
                     "post_processing": [pivot_operator(form_data, base), resample_operator(form_data, base),
                                         rolling_window_operator(form_data, base), flatten_operator(form_data, base)]}
        if form_data.get("aggregation") != "raw":
            return [trendline]
        # isRawMetric is always true here, so the second query has no time column and no post-processing
        # (its aggregationOperator branch never runs: the other aggregations are computed by the frontend).
        return [trendline, {**base, "columns": [], "is_timeseries": False, "post_processing": []}]

    return build_query_context(form_data, build)


def build_bubble(form_data: dict[str, Any]) -> dict[str, Any]:
    """Bubble buildQuery: entity and series are the columns; the first orderby item follows ``order_desc``."""
    columns = [*ensure_list(form_data.get("entity")), *ensure_list(form_data.get("series"))]

    def build(base: dict[str, Any]) -> list[Any]:
        orderby = base.get("orderby")
        return [{**base, "columns": columns,
                 "orderby": [[orderby[0], not base.get("order_desc")]] if orderby else UNSET}]

    return build_query_context(form_data, build)


def histogram_operator(form_data: dict[str, Any], query: dict[str, Any]) -> Any:
    """``histogramOperator``: ``bins`` is ``Number(bins)``, 5 when that is NaN."""
    bins = js_number(form_data["bins"]) if form_data.get("bins") is not None else (0 if "bins" in form_data else UNSET)
    return {"operation": "histogram", "options": {
        "column": column_label(form_data.get("column")),
        "groupby": [column_label(c) for c in ensure_list(form_data.get("groupby", []))],
        "bins": 5 if bins is UNSET or (isinstance(bins, float) and math.isnan(bins)) else bins,
        "cumulative": form_data.get("cumulative", UNSET),
        "normalize": form_data.get("normalize", UNSET),
    }}


def build_histogram(form_data: dict[str, Any]) -> dict[str, Any]:
    """Histogram buildQuery: the groupby columns and the binned column, without metrics."""
    columns = [*ensure_list(form_data.get("groupby", [])), form_data.get("column", UNSET)]
    return build_query_context(form_data, lambda base: [{
        **base, "columns": columns, "post_processing": [histogram_operator(form_data, base)], "metrics": UNSET}])


def build_heatmap(form_data: dict[str, Any]) -> dict[str, Any]:
    """Heatmap buildQuery: x axis and groupby columns, axis sorting and the rank of the metric."""
    metric = metric_label(form_data["metric"]) if form_data.get("metric") else UNSET
    columns = [*ensure_list(x_axis_column(form_data)), *ensure_list(form_data.get("groupby"))]
    orderby = []
    for sort, position in ((form_data.get("sort_x_axis"), 0), (form_data.get("sort_y_axis"), 1)):
        if sort:
            axis = columns[position] if position < len(columns) else UNSET
            orderby.append([metric if "value" in sort else axis, "asc" in sort])
    normalize_across = form_data.get("normalize_across")
    group_by = UNSET
    if normalize_across == "x":
        group_by = column_label(form_data.get("x_axis"))
    elif normalize_across == "y":
        group_by = column_label(form_data.get("groupby"))
    return build_query_context(form_data, lambda base: [{
        **base, "columns": columns, "orderby": orderby,
        "post_processing": [{"operation": "rank", "options": {"metric": metric, "group_by": group_by}}]}])


def build_default(form_data: dict[str, Any]) -> dict[str, Any]:
    """Plugins without a buildQuery (e.g. big_number_total) and legacy charts saved from Explore."""
    return build_query_context(form_data)


BUILD_QUERY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "big_number": build_big_number,
    "big_number_total": build_default,
    "box_plot": build_box_plot,
    "bubble_v2": build_bubble,
    "echarts_area": build_timeseries,
    "echarts_timeseries_bar": build_timeseries,
    "echarts_timeseries_line": build_timeseries,
    "echarts_timeseries": build_timeseries,
    "funnel": build_sorted_by_metric,
    "gauge_chart": build_sorted_by_metric,
    "heatmap_v2": build_heatmap,
    "histogram_v2": build_histogram,
    "mixed_timeseries": build_mixed_timeseries,
    "pie": build_pie,
    "pivot_table_v2": build_pivot_table_v2,
    "sunburst_v2": build_sorted_by_metric,
    "table": build_table,
    "treemap_v2": build_treemap,
    "word_cloud": build_word_cloud,
}


def query_context_for(form_data: dict[str, Any]) -> dict[str, Any]:
    """Query context the Superset UI derives from `form_data`, dispatching on ``viz_type``."""
    return BUILD_QUERY.get(str(form_data.get("viz_type")), build_default)(form_data)

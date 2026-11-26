"""Labels a chart asks the categorical color scale of a dashboard for (Superset 6.1.0 frontend).

On a dashboard, each chart plugin colors its series, slices or nodes through the categorical color scale
(``CategoricalColorScale.getColor(value, sliceId)``), which registers the label for the chart; the dashboard compares
the labels of its charts with ``json_metadata.shared_label_colors`` and ``map_label_colors``. This module predicts
those labels from the chart data API result (``POST /api/v1/chart/data`` with the chart's query context) and the
params as the plugin sees them (``Chart.explore_params()``), porting the label rules of each plugin's transformProps.
The sources are cited per viz_type (P is ``superset-frontend/plugins/plugin-chart-echarts/src``); the specification
is in issue #134.

Known limits: word_cloud registers only the words d3-cloud placed, which depends on the screen, so all the words of
the query are returned (a superset of what is drawn); the numeric node names of a sunburst are formatted with
``number_format`` in the frontend, here with JS ``String()``; forecasts and annotation layers are not covered.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from supersetapiplus.charts.build_query import column_label, ensure_list, metric_label

#: ``NULL_STRING`` (P/constants.ts): the name formatSeriesName gives a null value.
NULL_STRING = "<NULL>"
#: GenericDataType.Temporal of the chart data API ``coltypes``.
TEMPORAL_COLTYPE = 2
#: Suffixes of the forecast series (P/utils/forecast.ts, ForecastSeriesEnum); the confidence bands first.
FORECAST_SUFFIXES = ("__yhat_lower", "__yhat_upper", "__yhat")
#: DTTM_ALIAS: the time column of a query without an x axis.
DTTM_ALIAS = "__timestamp"

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")

Results = Sequence[dict[str, Any]]


# --- JavaScript String() and time formats ----------------------------------------------------------------------

def js_number(value: float) -> str:
    """``Number.prototype.toString()``: the shortest round-trip digits, as integer up to 1e21 and in exponent form
    below 1e-6."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0:
        return "0"
    sign, digits_tuple, exponent = Decimal(repr(float(value))).normalize().as_tuple()
    digits = "".join(map(str, digits_tuple))
    assert isinstance(exponent, int)
    point = exponent + len(digits)  # position of the decimal point from the first digit
    prefix = "-" if sign else ""
    if len(digits) <= point <= 21:
        return prefix + digits + "0" * (point - len(digits))
    if 0 < point <= 21:
        return f"{prefix}{digits[:point]}.{digits[point:]}"
    if -6 < point <= 0:
        return f"{prefix}0.{'0' * -point}{digits}"
    mantissa = digits[0] + (f".{digits[1:]}" if len(digits) > 1 else "")
    return f"{prefix}{mantissa}e{'+' if point - 1 >= 0 else '-'}{abs(point - 1)}"


def js_string(value: object) -> str:
    """``String(value)`` in JavaScript, for the values of a chart data API result (JSON)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return js_number(value)
    if isinstance(value, list):  # Array.prototype.toString: null and undefined as empty strings
        return ",".join("" if item is None else js_string(item) for item in value)
    return str(value)


def _directive(char: str, moment: datetime) -> str:
    hour12 = moment.hour % 12 or 12
    values = {"a": _WEEKDAYS[moment.weekday()][:3], "A": _WEEKDAYS[moment.weekday()], "b": _MONTHS[moment.month - 1][:3],
              "B": _MONTHS[moment.month - 1], "d": f"{moment.day:02d}", "e": f"{moment.day:2d}",
              "H": f"{moment.hour:02d}", "I": f"{hour12:02d}", "j": f"{moment.timetuple().tm_yday:03d}",
              "L": f"{moment.microsecond // 1000:03d}", "m": f"{moment.month:02d}", "M": f"{moment.minute:02d}",
              "p": "AM" if moment.hour < 12 else "PM", "S": f"{moment.second:02d}", "y": f"{moment.year % 100:02d}",
              "Y": str(moment.year), "%": "%"}
    return values.get(char, f"%{char}")


def d3_utc_format(specifier: str, moment: datetime) -> str:
    """``d3.utcFormat(specifier)`` for the directives of the Superset date formats (en-US)."""
    out, index = [], 0
    while index < len(specifier):
        if specifier[index] == "%" and index + 1 < len(specifier):
            out.append(_directive(specifier[index + 1], moment))
            index += 2
        else:
            out.append(specifier[index])
            index += 1
    return "".join(out)


def _smart_date_specifier(moment: datetime) -> str:
    """createMultiFormatter of smart_date (time-format/formatters/smartDate.ts), in UTC."""
    if moment.microsecond:
        return ".%Lms"
    if moment.second:
        return ":%Ss"
    if moment.minute:
        return "%I:%M"
    if moment.hour:
        return "%I %p"
    if moment.day != 1:
        return "%a %d" if moment.weekday() != 6 else "%b %d"  # d3 utcWeek starts on Sunday
    return "%B" if moment.month != 1 else "%Y"


def time_format(epoch_ms: float, date_format: str | None) -> str:
    """``getTimeFormatter(date_format)(date)`` (UTC); smart_date when the format is absent."""
    moment = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    if not date_format or date_format == "smart_date":
        return d3_utc_format(_smart_date_specifier(moment), moment)
    return d3_utc_format(date_format, moment)


def format_series_name(value: object, temporal: bool = False, date_format: str | None = None) -> str:
    """``formatSeriesName`` (P/utils/series.ts:720-752) with a time formatter and no number formatter."""
    if value is None:
        return NULL_STRING
    if isinstance(value, bool):
        return "true" if value else "false"
    if temporal and isinstance(value, (int, float)):
        return time_format(value, date_format)
    if isinstance(value, (int, float)):
        return js_number(value) if isinstance(value, float) else str(value)
    return str(value)


def _temporal_columns(result: dict[str, Any]) -> set[str]:
    """Columns typed Temporal in the result (the plugins' coltypeMapping)."""
    names, kinds = result.get("colnames") or [], result.get("coltypes") or []
    return {name for name, kind in zip(names, kinds, strict=False) if kind == TEMPORAL_COLTYPE}


def groupby_label(row: dict[str, Any], columns: Iterable[str], temporal: Iterable[str] = (),
                  date_format: str | None = None) -> str:
    """``extractGroupbyLabel`` (P/utils/series.ts:766-788): the formatted groupby values joined by ", "."""
    temporal = set(temporal)
    return ", ".join(format_series_name(row.get(column), column in temporal, date_format) for column in columns)


def _groupby(form_data: dict[str, Any], key: str = "groupby") -> list[str]:
    return [label for label in (column_label(column) for column in ensure_list(form_data.get(key))) if label]


def _rows(results: Results, index: int = 0) -> list[dict[str, Any]]:
    return list(results[index].get("data") or []) if len(results) > index else []


# --- per viz_type ------------------------------------------------------------------------------------------------

def _split_forecast(name: str) -> tuple[str, str]:
    for suffix in FORECAST_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    return name, ""


def _verbose_names(keys: Iterable[str], verbose_map: dict[str, str]) -> list[str]:
    """``rebaseForecastDatum`` (P/utils/forecast.ts:126-133): each key renamed to its verbose name."""
    names = []
    for key in keys:
        base, suffix = _split_forecast(key)
        names.append(f"{verbose_map[base]}{suffix}" if key != DTTM_ALIAS and base in verbose_map else key)
    return names


def original_series(name: str, time_compare: Sequence[str]) -> str:
    """``getOriginalSeries`` (superset-ui-chart-controls operators/utils/timeOffset.ts): the offsets removed."""
    for offset in time_compare:
        name = name.replace(f", {offset},", ",", 1).replace(f"{offset},", "", 1)
        name = name.replace(f"__{offset}", "", 1).replace(f", {offset}", "", 1)
    return name.strip()


def _has_offset(name: str, time_compare: Sequence[str]) -> bool:
    return any(f"{offset}," in name or f"__{offset}" in name or f", {offset}" in name for offset in time_compare)


def _extra_metric(form_data: dict[str, Any]) -> str | None:
    """``extractExtraMetrics``: the sort metric added to the query, not a series."""
    limit_metric = next(iter(ensure_list(form_data.get("timeseries_limit_metric"))), None)
    if limit_metric is None or ensure_list(form_data.get("groupby")):
        return None
    label = metric_label(limit_metric)
    metrics = {metric_label(metric) for metric in ensure_list(form_data.get("metrics"))}
    return label if label == form_data.get("x_axis_sort") and label not in metrics else None


def _x_axis(form_data: dict[str, Any]) -> str:
    """The label of the x axis column of a timeseries result (DTTM_ALIAS without an x axis)."""
    return (column_label(form_data["x_axis"]) if form_data.get("x_axis") else None) or DTTM_ALIAS


def _series_names(form_data: dict[str, Any], rows: list[dict[str, Any]], verbose_map: dict[str, str]) -> list[str]:
    """The series of a timeseries result: the columns minus the x axis and the extra metric (P/utils/series.ts)."""
    if not rows:
        return []
    excluded = {_x_axis(form_data), _extra_metric(form_data)}
    return _verbose_names([key for key in rows[0] if key not in excluded], verbose_map)


def _shift_color_key(name: str, names: list[str], form_data: dict[str, Any], inverted: dict[str, str]) -> str:
    """``colorScaleKey`` of Timeseries/transformProps.ts:440-473 (time_shift_color on)."""
    time_compare = [str(offset) for offset in ensure_list(form_data.get("time_compare"))]
    series = inverted.get(name, name)
    key = original_series(series, time_compare)
    metrics = ensure_list(form_data.get("metrics"))
    if _groupby(form_data) and time_compare and len(metrics) == 1:
        key = key.replace(f"{metric_label(metrics[0])}, ", "", 1)
    if series in time_compare:  # a series named as an offset takes the color of the first original series
        original = next((other for other in names if not _derived(inverted.get(other, other), time_compare)), None)
        if original is not None:
            key = original_series(inverted.get(original, original), time_compare)
    return key


def _derived(name: str, time_compare: Sequence[str]) -> bool:
    return name in time_compare or _has_offset(name, time_compare)


def timeseries_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """echarts_timeseries_line/_bar, echarts_area (P/Timeseries/transformProps.ts, transformers.ts:286-324)."""
    rows = _rows(results)
    names = _series_names(form_data, rows, verbose_map)
    inverted = {verbose: name for name, verbose in verbose_map.items()}
    stacked = bool(form_data.get("stack")) or form_data.get("viz_type") == "echarts_area"
    labels = []
    for name in names:
        base, suffix = _split_forecast(name)
        if stacked and suffix in FORECAST_SUFFIXES[:2]:  # confidence bands of a stack or area are not drawn
            continue
        labels.append(_shift_color_key(name, names, form_data, inverted) if form_data.get("time_shift_color")
                      else base)
    if form_data.get("color_by_primary_axis"):
        x_axis = _x_axis(form_data)
        labels.extend(NULL_STRING if row.get(x_axis) is None else js_string(row.get(x_axis)) for row in rows)
    return labels


def mixed_timeseries_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """mixed_timeseries (P/MixedTimeseries/transformProps.ts:463-478, 537-552): the series of queries A and B by
    their result column names, without a query suffix."""
    inverted = {verbose: name for name, verbose in verbose_map.items()}
    time_compare = [str(offset) for offset in ensure_list(form_data.get("time_compare"))]
    labels = []
    for index in (0, 1):
        for name in _series_names(form_data, _rows(results, index), verbose_map):
            labels.append(original_series(inverted.get(name, name), time_compare)
                          if form_data.get("time_shift_color") else name)
    return labels


def box_plot_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """box_plot (P/BoxPlot/transformProps.ts:113): the groupby label of each row, not the metric."""
    columns, temporal = _groupby(form_data), _temporal_columns(results[0]) if results else set()
    return [groupby_label(row, columns, temporal, form_data.get("date_format")) for row in _rows(results)]


def pie_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """pie (P/Pie/transformProps.ts:200-284): the groupby label of each slice; the rows grouped into "Other" (below
    ``threshold_for_other`` percent) are not registered, nor is "Other"."""
    columns, temporal = _groupby(form_data), _temporal_columns(results[0]) if results else set()
    threshold = form_data.get("threshold_for_other") or 0
    contribution = f"{metric_label(form_data.get('metric') or '')}__contribution"
    rows = [row for row in _rows(results)
            if not threshold or not row.get(contribution) or row[contribution] * 100 >= threshold]
    return [groupby_label(row, columns, temporal, form_data.get("date_format")) for row in rows]


def funnel_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """funnel (P/Funnel/transformProps.ts:174-189): extractGroupbyLabel without a temporal mapping."""
    return [groupby_label(row, _groupby(form_data)) for row in _rows(results)]


def gauge_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """gauge_chart (P/Gauge/transformProps.ts:175-184): the groupby values as an array, so String() joins them with
    "," and a null is empty."""
    columns = _groupby(form_data)
    return [js_string([row.get(column) for column in columns]) for row in _rows(results)]


def histogram_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """histogram_v2 (P/Histogram/transformProps.ts:91-102): the groupby values joined by ", " (Array.join), or the
    column label without groupby."""
    columns = _groupby(form_data)
    if not columns:
        return [column_label(form_data.get("column") or "") or ""]
    return [", ".join("" if row.get(column) is None else js_string(row.get(column)) for column in columns)
            for row in _rows(results)]


def bubble_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """bubble_v2 (P/Bubble/transformProps.ts:147-164): the series (or entity) value; any falsy value is <NULL>."""
    key = column_label(form_data.get("series") or form_data.get("entity") or "") or ""
    labels = []
    for row in _rows(results):
        value = row.get(key)
        falsy = value is None or value is False or value == "" or (isinstance(value, (int, float)) and
                                                                     (value == 0 or value != value))
        labels.append(NULL_STRING if falsy else js_string(value))
    return labels


def _node_labels(form_data: dict[str, Any], results: Results) -> list[str]:
    """The metric label and the name of every node of every level of the groupby tree (not the path)."""
    columns, temporal = _groupby(form_data, "columns" if "columns" in form_data else "groupby"), set()
    if results:
        temporal = _temporal_columns(results[0])
    labels = [metric_label(form_data.get("metric") or "") or ""]
    for column in columns:
        labels.extend(format_series_name(row.get(column), column in temporal, form_data.get("date_format"))
                      for row in _rows(results))
    return labels


def treemap_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """treemap_v2 (P/Treemap/transformProps.ts:180-234)."""
    return _node_labels({**form_data, "columns": ensure_list(form_data.get("groupby"))}, results)


def sunburst_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """sunburst_v2 (P/Sunburst/transformProps.ts:269-315): only when colored by category, i.e. without a secondary
    metric or with the same one (compared by identity in JS: two adhoc metric objects differ)."""
    metric, secondary = form_data.get("metric"), form_data.get("secondary_metric")
    if secondary and not (isinstance(metric, str) and metric == secondary):
        return []
    return _node_labels(form_data, results)


def word_cloud_labels(form_data: dict[str, Any], results: Results, verbose_map: dict[str, str]) -> list[str]:
    """word_cloud (plugin-chart-word-cloud/src/chart/WordCloud.tsx:174-178, 321): String() of the series value of
    every row (the plugin colors only the words placed, which depends on the screen)."""
    key = column_label(form_data.get("series") or "") or ""
    return [js_string(row.get(key)) for row in _rows(results)]


LabelRule = Callable[[dict[str, Any], Results, dict[str, str]], list[str]]

#: The rule of each modeled viz_type; None for those that register no label (sequential colors, tables, numbers).
LABEL_RULES: dict[str, LabelRule | None] = {
    "big_number": None,
    "big_number_total": None,
    "box_plot": box_plot_labels,
    "bubble_v2": bubble_labels,
    "cal_heatmap": None,
    "echarts_area": timeseries_labels,
    "echarts_timeseries": timeseries_labels,
    "echarts_timeseries_bar": timeseries_labels,
    "echarts_timeseries_line": timeseries_labels,
    "funnel": funnel_labels,
    "gauge_chart": gauge_labels,
    "heatmap_v2": None,
    "histogram_v2": histogram_labels,
    "mixed_timeseries": mixed_timeseries_labels,
    "pie": pie_labels,
    "pivot_table_v2": None,
    "sunburst_v2": sunburst_labels,
    "table": None,
    "treemap_v2": treemap_labels,
    "word_cloud": word_cloud_labels,
}


def color_labels(form_data: dict[str, Any], results: Results,
                 verbose_map: dict[str, str] | None = None) -> list[str] | None:
    """The labels a chart registers in the categorical color scale of a dashboard, normalized as the scale does
    (``String(value).trim()``) and without repeats, in first-seen order; None for a viz_type that registers none.

    `form_data` are the params as the plugin sees them (``Chart.explore_params()``), `results` the ``result`` of the
    chart data API for the chart's query context, `verbose_map` the dataset's verbose names (column or metric name ->
    verbose name). Raises ValueError for a viz_type the library does not model.
    """
    viz_type = str(form_data.get("viz_type"))
    if viz_type not in LABEL_RULES:
        raise ValueError(f"no color label rule for viz_type {viz_type!r}")
    rule = LABEL_RULES[viz_type]
    if rule is None:
        return None
    labels: dict[str, None] = {}
    for label in rule(form_data, results, verbose_map or {}):
        labels.setdefault(label.strip(), None)
    return list(labels)

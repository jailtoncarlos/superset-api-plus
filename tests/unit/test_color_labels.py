"""Labels each chart plugin registers in the categorical color scale (supersetapiplus.charts.color_labels): pure
logic on synthetic chart data API results, no HTTP. The rules are those of the Superset 6.1.0 transformProps cited
in the module (specification in issue #134)."""
import pytest

from supersetapiplus.charts.color_labels import (
    LABEL_RULES,
    color_labels,
    format_series_name,
    js_number,
    js_string,
    original_series,
    time_format,
)

JAN_1 = 1767225600000  # 2026-01-01T00:00:00Z (a Thursday)
DAY = 86400000


def result(rows, colnames=None, coltypes=None):
    colnames = colnames or (list(rows[0]) if rows else [])
    return {"colnames": colnames, "coltypes": coltypes or [1] * len(colnames), "data": rows}


@pytest.mark.parametrize(("value", "text"), [
    (1.0, "1"), (0.5, "0.5"), (-2.25, "-2.25"), (1e21, "1e+21"), (123456789012345680000.0, "123456789012345680000"),
    (1e-6, "0.000001"), (1e-7, "1e-7"), (1.5e-10, "1.5e-10"), (0.1 + 0.2, "0.30000000000000004"),
    (float("nan"), "NaN"), (float("-inf"), "-Infinity"), (0.0, "0")])
def test_numbers_are_written_as_javascript_does(value, text):
    assert js_number(value) == text


def test_string_of_values_and_arrays_is_the_javascript_one():
    assert [js_string(v) for v in (None, True, 3, 2.0, "x")] == ["null", "true", "3", "2", "x"]
    assert js_string(["a", None, 1, 2.5]) == "a,,1,2.5"


@pytest.mark.parametrize(("epoch_ms", "text"), [
    (JAN_1, "2026"), (JAN_1 + 31 * DAY, "February"), (JAN_1 + DAY, "Fri 02"), (JAN_1 + 3 * DAY, "Jan 04"),
    (JAN_1 + 3600000 * 13, "01 PM"), (JAN_1 + 60000 * 5, "12:05"), (JAN_1 + 7000, ":07s"), (JAN_1 + 7, ".007ms")])
def test_smart_date_picks_the_format_of_the_granularity_in_utc(epoch_ms, text):
    assert time_format(epoch_ms, "smart_date") == text


def test_a_date_format_is_applied_in_utc():
    assert time_format(JAN_1 + DAY, "%Y-%m-%d %H:%M") == "2026-01-02 00:00"
    assert time_format(JAN_1 + DAY, "%d/%m/%Y") == "02/01/2026"


@pytest.mark.parametrize(("epoch_ms", "specifier", "text"), [
    (JAN_1, "%Y-W%V", "2026-W01"), (JAN_1 + 4 * DAY, "%Y-W%V", "2026-W02"),
    (JAN_1 + 365 * DAY, "%G-W%V %g %u %w", "2026-W53 26 5 5"),  # 2027-01-01, a Friday in the last ISO week of 2026
    (JAN_1 + 3 * DAY, "%U %W %j %q", "01 00 004 1"), (JAN_1 + DAY, "%-d/%-m %_d|%e|%0e", "2/1  2| 2|02"),
    (JAN_1 + DAY + 47107007, "%x %X", "1/2/2026 1:05:07 PM"), (JAN_1 + DAY + 47107007, "%c", "1/2/2026, 1:05:07 PM"),
    (JAN_1 + 7, "%s %Q %f %L %Z", f"{JAN_1 // 1000} {JAN_1 + 7} 007000 007 +0000"),
    (JAN_1, "%k%%%", "k%")])
def test_custom_formats_take_every_d3_directive_and_padding_modifier(epoch_ms, specifier, text):
    assert time_format(epoch_ms, specifier) == text


def test_series_names_are_formatted_as_format_series_name():
    assert [format_series_name(v) for v in (None, False, 7, 2.0, "North")] == ["<NULL>", "false", "7", "2", "North"]
    assert format_series_name(JAN_1, temporal=True) == "2026"


def test_time_offsets_are_removed_from_the_series_name():
    assert original_series("SUM(x)__1 year ago", ["1 year ago"]) == "SUM(x)"
    assert original_series("SUM(x), 1 year ago, North", ["1 year ago"]) == "SUM(x), North"
    assert original_series("1 year ago, North", ["1 year ago"]) == "North"


def test_every_modeled_viz_type_has_a_rule():
    assert {"table", "pie", "word_cloud", "cal_heatmap"} <= set(LABEL_RULES)
    with pytest.raises(ValueError, match="no color label rule for viz_type 'sankey_v2'"):
        color_labels({"viz_type": "sankey_v2"}, [])


@pytest.mark.parametrize("viz_type", ["table", "pivot_table_v2", "big_number", "big_number_total", "heatmap_v2",
                                      "cal_heatmap"])
def test_charts_without_categorical_colors_register_no_label(viz_type):
    assert color_labels({"viz_type": viz_type}, [result([{"a": 1}])]) is None


def test_timeseries_series_are_the_columns_but_the_x_axis_renamed_by_verbose_names():
    rows = [{"day": JAN_1, "North": 1, "South ": 2}, {"day": JAN_1 + DAY, "North": 3, "South ": 4}]
    form_data = {"viz_type": "echarts_timeseries_bar", "x_axis": "day", "metrics": ["count"], "groupby": ["campus"]}
    assert color_labels(form_data, [result(rows)]) == ["North", "South"]  # trimmed as the color scale does
    assert color_labels(form_data, [result(rows)], {"North": "Norte"}) == ["Norte", "South"]


def test_timeseries_with_color_by_primary_axis_also_registers_the_x_values():
    rows = [{"campus": "North", "count": 1}, {"campus": None, "count": 2}]
    form_data = {"viz_type": "echarts_timeseries_bar", "x_axis": "campus", "metrics": ["count"],
                 "color_by_primary_axis": True}
    assert color_labels(form_data, [result(rows)]) == ["count", "North", "<NULL>"]


def test_time_shift_color_gives_derived_series_the_key_of_their_original():
    rows = [{"__timestamp": JAN_1, "SUM(x), North": 1, "1 year ago, North": 2}]
    form_data = {"viz_type": "echarts_timeseries_line", "metrics": ["SUM(x)"], "groupby": ["campus"],
                 "time_compare": ["1 year ago"], "time_shift_color": True}
    assert color_labels(form_data, [result(rows)]) == ["North"]
    assert color_labels({**form_data, "time_shift_color": False}, [result(rows)]) == ["SUM(x), North",
                                                                                     "1 year ago, North"]


def test_the_extra_sort_metric_is_not_a_series():
    rows = [{"__timestamp": JAN_1, "count": 1, "SUM(total)": 9}]
    form_data = {"viz_type": "echarts_timeseries_line", "metrics": ["count"], "timeseries_limit_metric": "SUM(total)",
                 "x_axis_sort": "SUM(total)"}
    assert color_labels(form_data, [result(rows)]) == ["count"]


def test_mixed_timeseries_shares_a_label_for_the_same_column_in_both_queries():
    query_a = result([{"__timestamp": JAN_1, "count": 1, "North": 2}])
    query_b = result([{"__timestamp": JAN_1, "count": 3}])
    assert color_labels({"viz_type": "mixed_timeseries"}, [query_a, query_b]) == ["count", "North"]


def test_box_plot_labels_are_the_groupby_values_of_each_row():
    rows = [{"campus": "North", "year": JAN_1, "count__mean": 1}, {"campus": None, "year": JAN_1, "count__mean": 2}]
    data = result(rows, coltypes=[1, 2, 0])
    form_data = {"viz_type": "box_plot", "groupby": ["campus", "year"], "metrics": ["count"]}
    assert color_labels(form_data, [data]) == ["North, 2026", "<NULL>, 2026"]
    assert color_labels({**form_data, "groupby": []}, [data]) == [""]


def test_pie_leaves_out_the_slices_grouped_into_other():
    rows = [{"campus": "North", "count": 90, "count__contribution": 0.9},
            {"campus": "South", "count": 10, "count__contribution": 0.1}]
    form_data = {"viz_type": "pie", "groupby": ["campus"], "metric": "count"}
    assert color_labels(form_data, [result(rows)]) == ["North", "South"]
    assert color_labels({**form_data, "threshold_for_other": 20}, [result(rows)]) == ["North"]


def test_funnel_writes_dates_as_numbers_and_gauge_joins_with_a_comma():
    rows = [{"campus": "North", "year": JAN_1, "count": 1}]
    assert color_labels({"viz_type": "funnel", "groupby": ["campus", "year"]},
                        [result(rows, coltypes=[1, 2, 0])]) == [f"North, {JAN_1}"]
    rows = [{"campus": "North", "kind": None, "count": 1}]
    assert color_labels({"viz_type": "gauge_chart", "groupby": ["campus", "kind"]}, [result(rows)]) == ["North,"]


def test_histogram_labels_are_the_groupby_values_or_the_column():
    rows = [{"campus": "North", "kind": None, "0 - 5": 1}]
    assert color_labels({"viz_type": "histogram_v2", "groupby": ["campus", "kind"], "column": "total"},
                        [result(rows)]) == ["North,"]
    assert color_labels({"viz_type": "histogram_v2", "column": "total"}, [result(rows)]) == ["total"]


def test_bubble_falsy_values_are_null():
    rows = [{"campus": "North"}, {"campus": 0}, {"campus": ""}]
    assert color_labels({"viz_type": "bubble_v2", "entity": "campus"}, [result(rows)]) == ["North", "<NULL>"]


def test_treemap_and_sunburst_register_the_metric_and_every_node_name():
    rows = [{"campus": "North", "kind": "a", "count": 1}, {"campus": "North", "kind": None, "count": 2}]
    assert color_labels({"viz_type": "treemap_v2", "groupby": ["campus", "kind"], "metric": "count"},
                        [result(rows)]) == ["count", "North", "a", "<NULL>"]
    sunburst = {"viz_type": "sunburst_v2", "columns": ["campus", "kind"], "metric": "count"}
    assert color_labels(sunburst, [result(rows)]) == ["count", "North", "a", "<NULL>"]
    assert color_labels({**sunburst, "secondary_metric": "SUM(total)"}, [result(rows)]) == []


def test_word_cloud_registers_every_word_of_the_query():
    rows = [{"campus": "North", "count": 1}, {"campus": None, "count": 2}]
    assert color_labels({"viz_type": "word_cloud", "series": "campus"}, [result(rows)]) == ["North", "null"]

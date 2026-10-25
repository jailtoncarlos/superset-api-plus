"""Chart types and the options of each plugin (legend, orientation, labels, stacking, pivot, box plot, calendar)."""
from enum import IntEnum

from supersetapiplus.core.enums import StringEnum, deprecate_members


class ChartType(StringEnum):
    PIE = 'pie'
    TABLE = 'table'
    TIMESERIES_BAR = 'echarts_timeseries_bar'
    PIVOT_TABLE_V2 = 'pivot_table_v2'
    BIG_NUMBER_TOTAL = 'big_number_total'
    BOX_PLOT = 'box_plot'
    CAL_HEATMAP = 'cal_heatmap'
    MIXED_TIMESERIES = 'mixed_timeseries'
    WORD_CLOUD = 'word_cloud'
    TREEMAP_V2 = 'treemap_v2'
    TIMESERIES_LINE = 'echarts_timeseries_line'
    AREA = 'echarts_area'
    BIG_NUMBER = 'big_number'
    FUNNEL = 'funnel'
    GAUGE = 'gauge_chart'
    BUBBLE_V2 = 'bubble_v2'
    HISTOGRAM_V2 = 'histogram_v2'
    HEATMAP_V2 = 'heatmap_v2'
    SUNBURST_V2 = 'sunburst_v2'


# Legacy viz types removed from Superset -> the type Superset migrated their charts to
# (superset/migrations/shared/migrate_viz/processors.py, 6.1.0; checked in test_enum_conformance.py).
# filter_box has no chart type: it was replaced by the dashboard native filters (UPDATING.md, #26328).
REMOVED_VIZ_TYPES: dict[str, str] = {
    "area": "echarts_area",
    "bar": "echarts_timeseries_bar",
    "bubble": "bubble_v2",
    "dist_bar": "echarts_timeseries_bar",
    "dual_line": "mixed_timeseries",
    "heatmap": "heatmap_v2",
    "histogram": "histogram_v2",
    "line": "echarts_timeseries_line",
    "pivot_table": "pivot_table_v2",
    "sankey": "sankey_v2",
    "sunburst": "sunburst_v2",
    "treemap": "treemap_v2",
}
REMOVED_WITHOUT_CHART_TYPE = {"filter_box": "dashboard native filters (json_metadata.add_native_filter)"}

#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset-frontend/plugins/plugin-chart-echarts/src/types.ts
class LegendType(StringEnum):
    PLAIN = 'plain'
    SCROLL = 'scroll'

class LegendOrientationType(StringEnum):
    BOTTOM = 'bottom'
    TOP = 'top'
    LEFT = 'left'
    RIGHT = 'right'

class TreemapLabelType(StringEnum):
    """treemap_v2 label_type (EchartsTreemapLabelType, plugin-chart-echarts Treemap/types.ts, Superset 6.1.0).

    The control lists 'Key' for the first option, which matches no case of the plugin (no label is shown);
    the enum keeps the plugin values, and a 'Key' read from Superset is kept as read."""
    KEY = 'key'
    VALUE = 'value'
    KEY_VALUE = 'key_value'


class SunburstLabelType(StringEnum):
    """sunburst_v2 label_type (EchartsSunburstLabelType, plugin-chart-echarts Sunburst/types.ts, Superset 6.1.0)."""
    KEY = 'key'
    VALUE = 'value'
    KEY_VALUE = 'key_value'


class FunnelLabelType(IntEnum):
    """funnel label_type and tooltip_label_type: the numeric enum EchartsFunnelLabelType (Funnel/types.ts,
    Superset 6.1.0), stored as its number."""
    KEY = 0
    VALUE = 1
    PERCENT = 2
    KEY_VALUE = 3
    KEY_PERCENT = 4
    KEY_VALUE_PERCENT = 5
    VALUE_PERCENT = 6


class FunnelPercentCalcType(StringEnum):
    """funnel percent_calculation_type (PercentCalcType, Funnel/types.ts, Superset 6.1.0)."""
    TOTAL = 'total'
    PREVIOUS_STEP = 'prev_step'
    FIRST_STEP = 'first_step'


class TimeseriesSeriesType(StringEnum):
    """Series style of the timeseries charts (EchartsTimeseriesSeriesType, Timeseries/types.ts, Superset 6.1.0);
    the area chart offers line, smooth and the three steps."""
    LINE = 'line'
    SCATTER = 'scatter'
    SMOOTH = 'smooth'
    BAR = 'bar'
    START = 'start'
    MIDDLE = 'middle'
    END = 'end'


class HeatmapSortAxis(StringEnum):
    """heatmap_v2 sort_x_axis / sort_y_axis (sortAxisChoices, Heatmap/controlPanel.tsx, Superset 6.1.0)."""
    ALPHA_ASC = 'alpha_asc'
    ALPHA_DESC = 'alpha_desc'
    VALUE_ASC = 'value_asc'
    VALUE_DESC = 'value_desc'


class HeatmapNormalizeAcross(StringEnum):
    """heatmap_v2 normalize_across (Heatmap/controlPanel.tsx, Superset 6.1.0)."""
    HEATMAP = 'heatmap'
    X = 'x'
    Y = 'y'


class HeatmapLegendType(StringEnum):
    """heatmap_v2 legend_type (Heatmap/controlPanel.tsx, Superset 6.1.0)."""
    CONTINUOUS = 'continuous'
    PIECEWISE = 'piecewise'


class RollingType(StringEnum):
    """rolling_type of the advanced analytics (big_number controlPanel, Superset 6.1.0); 'None' is a value."""
    NONE = 'None'
    MEAN = 'mean'
    SUM = 'sum'
    STD = 'std'
    CUMSUM = 'cumsum'


class BigNumberAggregation(StringEnum):
    """big_number aggregation (keys of aggregationChoices, superset-ui-chart-controls customControls.tsx,
    Superset 6.1.0): how the displayed value is computed from the trendline; raw queries the overall value."""
    RAW = 'raw'
    LAST_VALUE = 'LAST_VALUE'
    SUM = 'sum'
    MEAN = 'mean'
    MIN = 'min'
    MAX = 'max'
    MEDIAN = 'median'


class LabelType(StringEnum):
    CATEGORY_NAME = 'key'
    VALUE = 'value'
    PERCENTAGE = 'percent'
    CATEGORY_AND_VALUE = 'key_value'
    CATEGORY_AND_PERCENTAGE = 'key_percent'
    CATEGORY_VALUE_AND_PERCENTAGE = 'key_value_percent'
    VALUE_AND_PERCENTAGE = 'value_percent'
    TEMPLATE = 'template'

class Orientation(StringEnum):
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'

class SortSeriesType(StringEnum):
    NAME = 'name'
    MAX = 'max'
    MIN = 'min'
    SUM = 'sum'
    AVG = 'avg'

class StackStyleType(StringEnum):
    """Stack style (plugin-chart-echarts StackControlsValue). "No stack" is `null`, not a value of the enum."""
    STACK = 'Stack'
    STREAM = 'Stream'
    EXPAND = 'Expand'  # area charts only (AreaChartStackControlOptions)

class TitlePositionType(StringEnum):
    """Axis title position (superset-ui-chart-controls TITLE_POSITION_OPTIONS)."""
    LEFT = 'Left'
    TOP = 'Top'

class LabelRotation(IntEnum):
    """xAxisLabelRotation choices (plugin-chart-echarts controls.tsx)."""
    ZERO = 0
    FORTY_FIVE = 45
    NINETY = 90

class ComparisonColorScheme(StringEnum):
    """Table comparison colors (superset-ui-chart-controls ColorSchemeEnum)."""
    GREEN = 'Green'
    RED = 'Red'

class MetricsLayoutEnum(StringEnum):
    ROWS = 'ROWS'
    COLUMNS = 'COLUMNS'

class OrderType(StringEnum):
    KEY_A_TO_Z = 'key_a_to_z'
    KEY_Z_TO_A = 'key_z_to_a'
    VALUE_A_TO_Z = 'value_a_to_z'
    VALUE_Z_TO_A = 'value_z_to_a'

class PivotAggregateFunction(StringEnum):
    """pivot_table_v2 aggregators (controlPanel of plugin-chart-pivot-table, Superset 6.1.0)."""
    COUNT = 'Count'
    COUNT_UNIQUE_VALUES = 'Count Unique Values'
    LIST_UNIQUE_VALUES = 'List Unique Values'
    SUM = 'Sum'
    AVERAGE = 'Average'
    MEDIAN = 'Median'
    SAMPLE_VARIANCE = 'Sample Variance'
    SAMPLE_STANDARD_DEVIATION = 'Sample Standard Deviation'
    MINIMUM = 'Minimum'
    MAXIMUM = 'Maximum'
    FIRST = 'First'
    LAST = 'Last'
    SUM_AS_FRACTION_OF_TOTAL = 'Sum as Fraction of Total'
    SUM_AS_FRACTION_OF_ROWS = 'Sum as Fraction of Rows'
    SUM_AS_FRACTION_OF_COLUMNS = 'Sum as Fraction of Columns'
    COUNT_AS_FRACTION_OF_TOTAL = 'Count as Fraction of Total'
    COUNT_AS_FRACTION_OF_ROWS = 'Count as Fraction of Rows'
    COUNT_AS_FRACTION_OF_COLUMNS = 'Count as Fraction of Columns'

class WhiskerOptions(StringEnum):
    """box_plot whiskerOptions (plugin-chart-echarts BoxPlot controlPanel, Superset 6.1.0)."""
    TUKEY = 'Tukey'
    MIN_MAX = 'Min/max (no outliers)'
    PERCENTILES_2_98 = '2/98 percentiles'
    PERCENTILES_5_95 = '5/95 percentiles'
    PERCENTILES_9_91 = '9/91 percentiles'
    PERCENTILES_10_90 = '10/90 percentiles'

class CalendarDomain(StringEnum):
    """cal_heatmap domain_granularity (legacy-plugin-chart-calendar controlPanel, Superset 6.1.0)."""
    HOUR = 'hour'
    DAY = 'day'
    WEEK = 'week'
    MONTH = 'month'
    YEAR = 'year'

class CalendarSubdomain(StringEnum):
    """cal_heatmap subdomain_granularity (legacy-plugin-chart-calendar controlPanel, Superset 6.1.0)."""
    MIN = 'min'
    HOUR = 'hour'
    DAY = 'day'
    WEEK = 'week'
    MONTH = 'month'


# Old names, kept as aliases that emit DeprecationWarning.
deprecate_members(ChartType, {"PIVOT_TALBE_V2": "PIVOT_TABLE_V2"})
deprecate_members(LabelType, {"CATEGORI_VALUE_AND_PERCENTAG": "CATEGORY_VALUE_AND_PERCENTAGE"})

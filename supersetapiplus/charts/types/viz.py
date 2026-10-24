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

#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset-frontend/plugins/plugin-chart-echarts/src/types.ts
class LegendType(StringEnum):
    PLAIN = 'plain'
    SCROLL = 'scroll'

class LegendOrientationType(StringEnum):
    BOTTOM = 'bottom'
    TOP = 'top'
    LEFT = 'left'
    RIGHT = 'right'

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

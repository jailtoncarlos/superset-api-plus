from enum import IntEnum

from supersetapiplus.base.enum_str import StringEnum, deprecate_members
from supersetapiplus.deprecation import module_aliases


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


class NumberFormatType(StringEnum):
    """Number formats suggested by the UI (superset-ui-chart-controls D3_FORMAT_OPTIONS).

    The control is free-form: any d3 format is valid, so the members beyond the suggestions are d3 formats
    or NumberFormats ids of superset-ui-core. Values read from Superset are kept as stored.
    """
    ORIGINAL_VALUE = '~g'
    SMART_NUMBER = 'SMART_NUMBER'  # Adaptive formatting
    SMART_NUMBER_SIGNED = 'SMART_NUMBER_SIGNED'
    OVER_MAX_HIDDEN = 'OVER_MAX_HIDDEN'

    DOLLAR = '$,.2f'
    DOLLAR_SIGNED = '+$,.2f'
    DOLLAR_ROUND = '$,d'
    DOLLAR_ROUND_SIGNED = '+$,d'

    FLOAT_1_POINT = ',.1f'
    FLOAT_2_POINT = ',.2f'
    FLOAT_3_POINT = ',.3f'
    FLOAT = FLOAT_2_POINT

    FLOAT_SIGNED_1_POINT = '+,.1f'
    FLOAT_SIGNED_2_POINT = '+,.2f'
    FLOAT_SIGNED_3_POINT = '+,.3f'
    FLOAT_SIGNED = FLOAT_SIGNED_2_POINT

    INTEGER = ',d'
    INTEGER_SIGNED = '+,d'

    PERCENT_1_POINT = ',.1%'
    PERCENT_2_POINT = ',.2%'
    PERCENT_3_POINT = ',.3%'

    PERCENT_2_POINT_NO_GROUPING = '.2%'
    PERCENT_3_POINT_NO_GROUPING = '.3%'
    PRECISION_4 = '.4r'
    SIGNED = '+,'
    PERCENT_SIGNED_1_POINT = '+,.1%'
    PERCENT_SIGNED_2_POINT = '+,.2%'
    PERCENT_SIGNED_3_POINT = '+,.3%'
    PERCENT_SIGNED = PERCENT_SIGNED_2_POINT

    SI_1_DIGIT = '.1s'
    SI_2_DIGIT = '.2s'
    SI_3_DIGIT = '.3s'
    SI = SI_3_DIGIT

    DURATION = 'DURATION' #Duration in ms (66000 => 1m 6s)
    DURATION_SUB = 'DURATION_SUB' #Duration in ms (100.40008 => 100ms 400µs 80ns)
    DURATION_COL = 'DURATION_COL'  # Duration in ms (10500 => 0:10.5)
    MEMORY_DECIMAL = 'MEMORY_DECIMAL'
    MEMORY_BINARY = 'MEMORY_BINARY'
    MEMORY_TRANSFER_RATE_DECIMAL = 'MEMORY_TRANSFER_RATE_DECIMAL'
    MEMORY_TRANSFER_RATE_BINARY = 'MEMORY_TRANSFER_RATE_BINARY'


class DateFormatType(StringEnum):
    """Time formats suggested by the UI (superset-ui-chart-controls D3_TIME_FORMAT_OPTIONS); free-form control."""
    SMART_DATE = 'smart_date'
    DATABASE_DATETIME = '%Y-%m-%d %H:%M:%S'
    DATABASE_DATETIME_REVERSE = '%d-%m-%Y %H:%M:%S'
    US_DATE = '%m/%d/%Y'
    INTERNATIONAL_DATE = '%d/%m/%Y'
    DOTTED_DATE = '%d.%m.%Y'
    DATABASE_DATE = '%Y-%m-%d'
    TIME = '%H:%M:%S'


class TimeGrain(StringEnum):
    SECOND = "PT1S"
    FIVE_SECONDS = "PT5S"
    THIRTY_SECONDS = "PT30S"
    MINUTE = "PT1M"
    FIVE_MINUTES = "PT5M"
    TEN_MINUTES = "PT10M"
    FIFTEEN_MINUTES = "PT15M"
    THIRTY_MINUTES = "PT30M"
    # HALF_HOUR and QUARTER_YEAR are official constants, but the chart data schema only accepts them when
    # TIME_GRAIN_ADDONS is configured in Superset (they are not in builtin_time_grains).
    HALF_HOUR = "PT0.5H"
    HOUR = "PT1H"
    SIX_HOURS = "PT6H"
    DAY = "P1D"
    WEEK = "P1W"
    WEEK_STARTING_SUNDAY = "1969-12-28T00:00:00Z/P1W"
    WEEK_STARTING_MONDAY = "1969-12-29T00:00:00Z/P1W"
    WEEK_ENDING_SATURDAY = "P1W/1970-01-03T00:00:00Z"
    WEEK_ENDING_SUNDAY = "P1W/1970-01-04T00:00:00Z"
    MONTH = "P1M"
    QUARTER = "P3M"
    QUARTER_YEAR = "P0.25Y"
    YEAR = "P1Y"


class LabelType(StringEnum):
    CATEGORY_NAME = 'key'
    VALUE = 'value'
    PERCENTAGE = 'percent'
    CATEGORY_AND_VALUE = 'key_value'
    CATEGORY_AND_PERCENTAGE = 'key_percent'
    CATEGORY_VALUE_AND_PERCENTAGE = 'key_value_percent'
    VALUE_AND_PERCENTAGE = 'value_percent'
    TEMPLATE = 'template'


class FilterOperatorType(StringEnum):
    """Adhoc filter operators (superset/utils/core.py FilterOperator, Superset 6.1.0).

    The member name becomes the filter's `operatorId` and follows the frontend `Operators` enum
    (src/explore/constants.ts); the old names are kept as aliases.
    """
    EQUALS = '=='
    NOT_EQUALS = '!='
    LESS_THAN = '<'
    LESS_THAN_OR_EQUAL = '<='
    GREATER_THAN = '>'
    GREATER_THAN_OR_EQUAL = '>='
    IN = 'IN'
    NOT_IN = 'NOT IN'
    LIKE = 'LIKE'
    NOT_LIKE = 'NOT LIKE'
    ILIKE = 'ILIKE'
    NOT_ILIKE = 'NOT ILIKE'
    IS_NOT_NULL = 'IS NOT NULL'
    IS_NULL = 'IS NULL'
    LATEST_PARTITION = 'LATEST PARTITION'
    IS_TRUE = 'IS TRUE'
    IS_FALSE = 'IS FALSE'
    TEMPORAL_RANGE = 'TEMPORAL_RANGE'


class FilterExpressionType(StringEnum):
    SIMPLE = 'SIMPLE'
    CUSTOM_SQL = 'SQL'


class ColumnType(StringEnum):
    BASE_AXIS = 'BASE_AXIS'
    SERIES = 'SERIES'


class SqlMapType(StringEnum):
    """Deprecated: not a Superset enum. A column `type` is the native database type (free text, e.g.
    "VARCHAR(255)"); `AdhocMetricColumn.type` is a `str`. Kept so that existing imports keep working."""
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    VARCHAR = "VARCHAR"
    STRING = "STRING"
    TEXT = "TEXT"
    BIGINT = "BIGINT"
    FLOAT = "FLOAT"
    FLOAT64 = "FLOAT64"
    DOUBLE_PRECISION = "DOUBLE PRECISION"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP_WITHOUT_TIME_ZONE = "TIMESTAMP WITHOUT TIME ZONE"
    TIMESTAMP_WITH_TIME_ZONE = "TIMESTAMP WITH TIME ZONE"


class GenericDataType(IntEnum):
    NUMERIC = 0
    STRING = 1
    TEMPORAL = 2
    BOOLEAN = 3
    # ARRAY = 4     # Mapping all the complex data types to STRING for now
    # JSON = 5      # and leaving these as a reminder.
    # MAP = 6
    # ROW = 7


class FilterClausesType(StringEnum):
    HAVING = 'HAVING'
    WHERE = 'WHERE'


class QueryModeType(StringEnum):
    RAW = "raw"
    AGGREGATE = "aggregate"


class MetricType(StringEnum):
    """Aggregate of a simple adhoc metric (src/explore/constants.ts AGGREGATES, Superset 6.1.0).

    The backend looks the value up as is (`sqla_aggregations[metric["aggregate"]]`), so it is uppercase.
    """
    AVG = "AVG"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    MAX = "MAX"
    MIN = "MIN"
    SUM = "SUM"


class CurrencyCodeType(StringEnum):
    """Currency of a number format: ISO 4217 codes, offered in the UI from the CURRENCIES setting
    (superset/config.py), plus AUTO (superset-ui-core AUTO_CURRENCY_SYMBOL: currency taken from a column)."""
    AUTO = 'AUTO'
    AED = 'AED'
    AFN = 'AFN'
    ALL = 'ALL'
    AMD = 'AMD'
    ANG = 'ANG'
    AOA = 'AOA'
    ARS = 'ARS'
    AUD = 'AUD'
    AWG = 'AWG'
    AZN = 'AZN'
    BAM = 'BAM'
    BBD = 'BBD'
    BDT = 'BDT'
    BGN = 'BGN'
    BHD = 'BHD'
    BIF = 'BIF'
    BMD = 'BMD'
    BND = 'BND'
    BOB = 'BOB'
    BRL = 'BRL'
    BSD = 'BSD'
    BTN = 'BTN'
    BWP = 'BWP'
    BYN = 'BYN'
    BZD = 'BZD'
    CAD = 'CAD'
    CDF = 'CDF'
    CHF = 'CHF'
    CLP = 'CLP'
    CNY = 'CNY'
    COP = 'COP'
    CRC = 'CRC'
    CUC = 'CUC'
    CUP = 'CUP'
    CVE = 'CVE'
    CZK = 'CZK'
    DJF = 'DJF'
    DKK = 'DKK'
    DOP = 'DOP'
    DZD = 'DZD'
    EGP = 'EGP'
    ERN = 'ERN'
    ETB = 'ETB'
    EUR = 'EUR'
    FJD = 'FJD'
    FKP = 'FKP'
    GBP = 'GBP'
    GEL = 'GEL'
    GHS = 'GHS'
    GIP = 'GIP'
    GMD = 'GMD'
    GNF = 'GNF'
    GTQ = 'GTQ'
    GYD = 'GYD'
    HKD = 'HKD'
    HNL = 'HNL'
    HRK = 'HRK'
    HTG = 'HTG'
    HUF = 'HUF'
    IDR = 'IDR'
    ILS = 'ILS'
    INR = 'INR'
    IQD = 'IQD'
    IRR = 'IRR'
    ISK = 'ISK'
    JMD = 'JMD'
    JOD = 'JOD'
    JPY = 'JPY'
    KES = 'KES'
    KGS = 'KGS'
    KHR = 'KHR'
    KMF = 'KMF'
    KPW = 'KPW'
    KRW = 'KRW'
    KWD = 'KWD'
    KYD = 'KYD'
    KZT = 'KZT'
    LAK = 'LAK'
    LBP = 'LBP'
    LKR = 'LKR'
    LRD = 'LRD'
    LSL = 'LSL'
    LYD = 'LYD'
    MAD = 'MAD'
    MDL = 'MDL'
    MGA = 'MGA'
    MKD = 'MKD'
    MMK = 'MMK'
    MNT = 'MNT'
    MOP = 'MOP'
    MRU = 'MRU'
    MUR = 'MUR'
    MVR = 'MVR'
    MWK = 'MWK'
    MXN = 'MXN'
    MYR = 'MYR'
    MZN = 'MZN'
    NAD = 'NAD'
    NGN = 'NGN'
    NIO = 'NIO'
    NOK = 'NOK'
    NPR = 'NPR'
    NZD = 'NZD'
    OMR = 'OMR'
    PAB = 'PAB'
    PEN = 'PEN'
    PGK = 'PGK'
    PHP = 'PHP'
    PKR = 'PKR'
    PLN = 'PLN'
    PYG = 'PYG'
    QAR = 'QAR'
    RON = 'RON'
    RSD = 'RSD'
    RUB = 'RUB'
    RWF = 'RWF'
    SAR = 'SAR'
    SBD = 'SBD'
    SCR = 'SCR'
    SDG = 'SDG'
    SEK = 'SEK'
    SGD = 'SGD'
    SHP = 'SHP'
    SLL = 'SLL'
    SOS = 'SOS'
    SRD = 'SRD'
    SSP = 'SSP'
    STN = 'STN'
    SVC = 'SVC'
    SYP = 'SYP'
    SZL = 'SZL'
    THB = 'THB'
    TJS = 'TJS'
    TMT = 'TMT'
    TND = 'TND'
    TOP = 'TOP'
    TRY = 'TRY'
    TTD = 'TTD'
    TWD = 'TWD'
    TZS = 'TZS'
    UAH = 'UAH'
    UGX = 'UGX'
    USD = 'USD'
    UYU = 'UYU'
    UZS = 'UZS'
    VES = 'VES'
    VND = 'VND'
    VUV = 'VUV'
    WST = 'WST'
    XAF = 'XAF'
    XCD = 'XCD'
    XOF = 'XOF'
    XPF = 'XPF'
    YER = 'YER'
    ZAR = 'ZAR'
    ZMW = 'ZMW'
    ZWL = 'ZWL'


class CurrencyPositionType(StringEnum):
    PREFIX = 'prefix'
    SUFFIX = 'suffix'


class HorizontalAlignType(StringEnum):
    LEFT = 'left'
    RIGHT = 'right'
    CENTER = 'center'


class Orientation(StringEnum):
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'


class ContributionType(StringEnum):
    ROW = 'row'
    COLUMN = 'column'


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


class ComparisonType(StringEnum):
    VALUES = 'values'
    DIFFERENCE = 'difference'
    PERCENTAGE = 'percentage'
    RATIO = 'ratio'


class ResultFormat(StringEnum):
    """superset/common/chart_data.py ChartDataResultFormat (6.1.0)."""
    CSV = 'csv'
    JSON = 'json'
    XLSX = 'xlsx'


class ResultType(StringEnum):
    """superset/common/chart_data.py ChartDataResultType (6.1.0)."""
    COLUMNS = 'columns'
    FULL = 'full'
    QUERY = 'query'
    RESULTS = 'results'
    SAMPLES = 'samples'
    TIMEGRAINS = 'timegrains'
    POST_PROCESSED = 'post_processed'
    DRILL_DETAIL = 'drill_detail'


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


class PercentMetricCalculation(StringEnum):
    """Table percent_metric_calculation (plugin-chart-table controlPanel, Superset 6.1.0)."""
    ROW_LIMIT = 'row_limit'
    ALL_RECORDS = 'all_records'


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
deprecate_members(FilterOperatorType, {"NOT_EQUAL": "NOT_EQUALS"})
__getattr__ = module_aliases(__name__, globals(), {
    "StackStylyType": "StackStyleType", "TitlepositionType": "TitlePositionType",
    "CurrentPositionType": "CurrencyPositionType"})

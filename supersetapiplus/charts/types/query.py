"""Query building: query mode, aggregates, columns, result format and type, comparison and contribution."""
from enum import IntEnum

from supersetapiplus.core.enums import StringEnum


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

class ColumnType(StringEnum):
    BASE_AXIS = 'BASE_AXIS'
    SERIES = 'SERIES'

class GenericDataType(IntEnum):
    NUMERIC = 0
    STRING = 1
    TEMPORAL = 2
    BOOLEAN = 3
    # ARRAY = 4     # Mapping all the complex data types to STRING for now
    # JSON = 5      # and leaving these as a reminder.
    # MAP = 6
    # ROW = 7

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

class ComparisonType(StringEnum):
    VALUES = 'values'
    DIFFERENCE = 'difference'
    PERCENTAGE = 'percentage'
    RATIO = 'ratio'

class ContributionType(StringEnum):
    ROW = 'row'
    COLUMN = 'column'

class PercentMetricCalculation(StringEnum):
    """Table percent_metric_calculation (plugin-chart-table controlPanel, Superset 6.1.0)."""
    ROW_LIMIT = 'row_limit'
    ALL_RECORDS = 'all_records'

# Configure logging
import logging

from supersetapiplus.charts.charts import Chart
from supersetapiplus.client import SupersetClient
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.core.types import DatasourceType
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.layout import ChartRef, DashboardLayout
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.resources.databases import Database
from supersetapiplus.resources.datasets import Dataset
from supersetapiplus.resources.saved_queries import SavedQuery

# What applications import; the modules keep their own paths (e.g. supersetapiplus.charts.charts.Chart).
__all__ = [
    "Chart", "ChartRef", "Dashboard", "DashboardLayout", "DataSource", "Database", "Dataset", "DatasourceType",
    "QueryOperator", "QueryStringFilter", "SavedQuery", "SupersetClient",
]

# The library does not configure application logging (no basicConfig); it only avoids the
# "No handlers could be found" warning when the application configures no handler.
logging.getLogger(__name__).addHandler(logging.NullHandler())

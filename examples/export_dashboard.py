"""Export a dashboard (ZIP with the dashboard, charts, datasets and databases).

Usage: python examples/export_dashboard.py "<dashboard title>" <file.zip>
"""
import os
import sys

from supersetapiplus.client import SupersetClient
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

# Connection read from the environment: SUPERSET_URL, SUPERSET_USERNAME and SUPERSET_PASSWORD.
client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
client.enable_session_mode()  # cookie + CSRF; required when the Public role has permissions (Superset 6.x)


def equals_filter(column: str, value: str) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(column, QueryOperator.EQUAL, value)
    return f


title, target = sys.argv[1:3]
dashboard = client.dashboards.find_one(equals_filter("dashboard_title", title))
client.dashboards.export([dashboard.id], target)
print(f"dashboard {dashboard.id} exported to {target}")

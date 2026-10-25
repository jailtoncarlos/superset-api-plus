"""Change the label colors of a dashboard.

Usage: python examples/change_colors.py "<dashboard title>" "<label>" "<hex color>"
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


title, label, color = sys.argv[1:4]
dashboard = client.dashboards.find_one(equals_filter("dashboard_title", title), full=True)

print("before:", dashboard.colors)
dashboard.update_colors({label: color})
dashboard.save()

print("after:", client.dashboards.get(dashboard.id).colors)

"""Connect to Superset and list counts and a few charts.

Usage: python examples/quickstart.py
"""
import os

from supersetapiplus.client import SupersetClient
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

# Connection read from the environment: SUPERSET_URL, SUPERSET_USERNAME and SUPERSET_PASSWORD.
client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
client.enable_session_mode()  # cookie + CSRF; required when the Public role has permissions (Superset 6.x)


def equals_filter(column: str, value: str) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(column, QueryOperator.EQUAL, value)
    return f


print("charts:", client.charts.count(), "| dashboards:", client.dashboards.count())
for chart in client.charts.find(QueryStringFilter(), columns=["id", "slice_name", "viz_type"], page_size=10):
    print(chart.id, chart.viz_type, chart.slice_name)

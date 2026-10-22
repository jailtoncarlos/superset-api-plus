"""Export a dataset (ZIP with the dataset and the database).

Usage: python examples/export_dataset.py <table name> <file.zip>
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


table, target = sys.argv[1:3]
dataset = client.datasets.find_one(equals_filter("table_name", table))
client.datasets.export([dataset.id], target)
print(f"dataset {dataset.id} exported to {target}")

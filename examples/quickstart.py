"""Conecta ao Superset e lista contagens e alguns gráficos.

Uso: python examples/quickstart.py
"""
import os

from supersetapiplus.client import SupersetClient
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

# Conexão lida do ambiente: SUPERSET_URL, SUPERSET_USERNAME e SUPERSET_PASSWORD.
client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
client.enable_session_mode()  # cookie + CSRF; necessário quando o papel Public tem permissões (Superset 6.x)


def filtro(coluna: str, valor: str) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(coluna, QueryOperator.EQUAL, valor)
    return f


print("charts:", client.charts.count(), "| dashboards:", client.dashboards.count())
for chart in client.charts.find(QueryStringFilter(), columns=["id", "slice_name", "viz_type"], page_size=10):
    print(chart.id, chart.viz_type, chart.slice_name)

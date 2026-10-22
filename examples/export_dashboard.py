"""Exporta um dashboard (ZIP com o dashboard, gráficos, datasets e databases).

Uso: python examples/export_dashboard.py "<título do dashboard>" <arquivo.zip>
"""
import os
import sys

from supersetapiplus.client import SupersetClient
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

# Conexão lida do ambiente: SUPERSET_URL, SUPERSET_USERNAME e SUPERSET_PASSWORD.
client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"], os.environ["SUPERSET_PASSWORD"])
client.enable_session_mode()  # cookie + CSRF; necessário quando o papel Public tem permissões (Superset 6.x)


def filtro(coluna: str, valor: str) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(coluna, QueryOperator.EQUAL, valor)
    return f


titulo, destino = sys.argv[1:3]
dashboard = client.dashboards.find_one(filtro("dashboard_title", titulo))
client.dashboards.export([dashboard.id], destino)
print(f"dashboard {dashboard.id} exportado em {destino}")

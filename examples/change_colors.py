"""Altera as cores de rótulos e o título de um dashboard.

Uso: python examples/change_colors.py "<título do dashboard>" "<rótulo>" "<cor hex>"
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


titulo, rotulo, cor = sys.argv[1:4]
dashboard = client.dashboards.find_one(filtro("dashboard_title", titulo), full=True)

print("antes:", dashboard.colors)
dashboard.update_colors({rotulo: cor})
dashboard.save()

print("depois:", client.dashboards.get(dashboard.id).colors)

"""Exporta um dataset (ZIP com o dataset e o database).

Uso: python examples/export_dataset.py <nome da tabela> <arquivo.zip>
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


tabela, destino = sys.argv[1:3]
dataset = client.datasets.find_one(filtro("table_name", tabela))
client.datasets.export([dataset.id], destino)
print(f"dataset {dataset.id} exportado em {destino}")

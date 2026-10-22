"""Conformidade com a especificação OpenAPI oficial do Superset (recorte em tests/fixtures).

Para cada recurso que a biblioteca grava, o payload de criação (POST) e de alteração (PUT)
precisa conter só campos aceitos pelo schema `{Recurso}RestApi.post/.put`, incluir os
obrigatórios e respeitar o tipo declarado. As rotas chamadas precisam existir com o método usado.

Para validar outra versão do Superset, gere um novo recorte com bin/scripts/extrair_openapi.py
e aponte SPEC para ele.
"""
import json
import re
from pathlib import Path

import pytest
import requests_mock as rm

from supersetapiplus.charts.table import TableChart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.saved_queries import SavedQuery

SPEC = json.loads((Path(__file__).parent.parent / "fixtures" / "superset_openapi_6.1.0.json").read_text())
HOST = "https://superset.exemplo"
API = f"{HOST}/api/v1"

TIPOS_JSON = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict, "number": (int, float)}

PARAMS = {"datasource": "1__table", "viz_type": "table", "query_mode": "aggregate",
          "groupby": ["campus"], "metrics": ["count"], "row_limit": 100}

# Objeto como o usuário cria (POST) e como chega da API num GET (PUT), por recurso.
RECURSOS = {
    "chart": ("ChartRestApi",
              lambda: TableChart.from_json({"slice_name": "Novo", "viz_type": "table", "params": json.dumps(PARAMS),
                                            "query_context": None, "datasource_id": 1, "datasource_type": "table"}),
              {"id": 9, "slice_name": "G", "viz_type": "table", "params": json.dumps(PARAMS), "query_context": None,
               "description": None, "cache_timeout": None, "dashboards": [], "url": "/explore/?slice_id=9",
               "thumbnail_url": "/t", "changed_on_delta_humanized": "1 day ago", "owners": [{"id": 1}],
               "tags": []}),
    "dashboard": ("DashboardRestApi",
                  lambda: Dashboard(dashboard_title="Painel", published=True, slug="painel"),
                  {"id": 9, "dashboard_title": "Painel", "published": True, "slug": "painel", "css": "",
                   "json_metadata": json.dumps({"color_scheme": "supersetColors"}),
                   "position_json": json.dumps({
                       "DASHBOARD_VERSION_KEY": "v2",
                       "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"], "parents": []},
                       "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": [], "parents": ["ROOT_ID"]}}),
                   "url": "/superset/dashboard/9/", "thumbnail_url": "/t", "owners": [], "roles": [],
                   "changed_by_name": "x", "charts": ["G"]}),
    "dataset": ("DatasetRestApi",
                lambda: Dataset(table_name="vw_respostas", schema="aai", database_id=1, sql="select 1"),
                {"id": 9, "table_name": "vw_respostas", "schema": "aai", "sql": "select 1", "kind": "virtual",
                 "description": None, "datasource_type": "table", "database": {"id": 1, "database_name": "dw"},
                 "columns": [{"column_name": "campus"}], "metrics": [], "owners": []}),
    "database": ("DatabaseRestApi",
                 lambda: Database(database_name="dw", sqlalchemy_uri="postgresql://u:p@h/db"),
                 {"id": 9, "database_name": "dw", "sqlalchemy_uri": "postgresql://u:XXXXXXXXXX@h/db",
                  "allow_ctas": False, "allow_cvas": False, "allow_dml": False, "allow_run_async": False,
                  "expose_in_sqllab": True, "extra": "{}", "backend": "postgresql"}),
    "saved_query": ("SavedQueryRestApi",
                    lambda: SavedQuery(label="Consulta", sql="select 1", db_id=1, schema="aai"),
                    {"id": 9, "label": "Consulta", "sql": "select 1", "schema": "aai", "description": "",
                     "database": {"id": 1}, "db_id": 1}),
}


def fabrica(client, recurso):
    return {"chart": client.charts, "dashboard": client.dashboards, "dataset": client.datasets,
            "database": client.databases, "saved_query": client.saved_queries}[recurso]


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "t"})
        m.get(f"{API}/security/csrf_token/", json={"result": "c"})
        m.get(re.compile(rf"{API}/\w+/_info"), json={"add_columns": [], "edit_columns": []})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robo", "senha")


def violacoes(payload: dict, schema: dict, obrigatorios: bool) -> list[str]:
    erros = [f"campo não aceito: {k}" for k in payload if k not in schema["properties"]]
    if obrigatorios:
        erros += [f"obrigatório ausente: {k}" for k in schema["required"] if k not in payload]
    for nome, valor in payload.items():
        prop = schema["properties"].get(nome, {})
        tipo = TIPOS_JSON.get(prop.get("type"))
        if tipo and valor is not None and not isinstance(valor, tipo):
            erros.append(f"{nome}: esperado {prop['type']}, enviado {type(valor).__name__} ({valor!r:.60})")
        if valor is None and tipo and not prop.get("nullable"):
            erros.append(f"{nome}: null não permitido")
    return erros


@pytest.mark.parametrize("recurso", RECURSOS)
def test_post_respeita_o_schema(recurso, client, mock):
    api, novo, _ = RECURSOS[recurso]
    factory = fabrica(client, recurso)
    mock.post(factory.base_url, json={"id": 1, "result": {}})

    factory.add(novo())

    assert violacoes(mock.last_request.json(), SPEC["schemas"][f"{api}.post"], obrigatorios=True) == []


@pytest.mark.parametrize("recurso", RECURSOS)
def test_put_respeita_o_schema(recurso, client, mock):
    api, _, lido = RECURSOS[recurso]
    factory = fabrica(client, recurso)
    mock.get(f"{factory.base_url}9", json={"id": 9, "result": lido})
    mock.put(f"{factory.base_url}9", json={"id": 9, "result": {}})

    factory.get(9).save()

    assert violacoes(mock.last_request.json(), SPEC["schemas"][f"{api}.put"], obrigatorios=False) == []


def caminhos_na_spec(url: str) -> list[str]:
    """Paths da spec compatíveis com a URL chamada (ids e slugs casam com os parâmetros)."""
    path = "/" + url.split(HOST, 1)[1].lstrip("/").split("?")[0]
    compativeis = []
    for candidato in SPEC["paths"]:
        padrao = re.sub(r"\\{[^}]+\\}", r"[^/]+", re.escape(candidato))
        if re.fullmatch(padrao, path):
            compativeis.append(candidato)
    return compativeis


ROTAS = [
    ("get", lambda c: c.charts.base_url), ("post", lambda c: c.charts.base_url),
    ("get", lambda c: f"{c.charts.base_url}9"), ("put", lambda c: f"{c.charts.base_url}9"),
    ("delete", lambda c: f"{c.charts.base_url}9"), ("get", lambda c: c.charts.info_url),
    ("get", lambda c: c.charts.export_url), ("post", lambda c: c.charts.import_url),
    ("get", lambda c: c.dashboards.base_url), ("post", lambda c: c.dashboards.base_url),
    ("get", lambda c: f"{c.dashboards.base_url}9"), ("put", lambda c: f"{c.dashboards.base_url}9"),
    ("get", lambda c: f"{c.dashboards.base_url}9/charts"),
    ("get", lambda c: c.datasets.base_url), ("post", lambda c: c.datasets.base_url),
    ("put", lambda c: f"{c.datasets.base_url}9"),
    ("get", lambda c: c.databases.base_url), ("post", lambda c: c.databases.base_url),
    ("put", lambda c: f"{c.databases.base_url}9"), ("post", lambda c: c.databases.test_connection_url),
    ("get", lambda c: c.saved_queries.base_url), ("post", lambda c: c.saved_queries.base_url),
    ("get", lambda c: c.assets.export_url), ("post", lambda c: c.login_endpoint),
    ("post", lambda c: c.refresh_endpoint), ("get", lambda c: c.join_urls(c.base_url, "security/csrf_token/")),
]


@pytest.mark.parametrize("metodo,url", ROTAS, ids=[f"{m}-{i}" for i, (m, _) in enumerate(ROTAS)])
def test_rotas_chamadas_existem_na_spec(metodo, url):
    client = SupersetClient(HOST, "robo", "senha")
    chamada = url(client)

    caminhos = caminhos_na_spec(chamada)

    assert caminhos, f"rota inexistente na spec: {chamada}"
    assert any(metodo in SPEC["paths"][c] for c in caminhos), f"{metodo.upper()} não existe em {caminhos}"


def test_execucao_de_sql_usa_rota_da_spec():
    client = SupersetClient(HOST, "robo", "senha")

    assert caminhos_na_spec(client._sql_endpoint)


@pytest.mark.parametrize("recurso", RECURSOS)
def test_campos_declarados_nos_modelos_sao_os_da_spec(recurso):
    api, novo, _ = RECURSOS[recurso]
    modelo = type(novo())

    assert set(modelo.POST_FIELDS) == set(SPEC["schemas"][f"{api}.post"]["properties"])
    assert set(modelo.PUT_FIELDS) == set(SPEC["schemas"][f"{api}.put"]["properties"])

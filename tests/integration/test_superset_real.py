"""Integração contra um Superset real, autenticando por sessão (cookie + CSRF).

Stack de testes (docker-compose.yml, configurada pelo .env copiado de .env.example):
    docker compose -p superset-api-plus up -d --build
    SUPERSET_INTEGRATION=1 pytest tests/integration -v
    docker compose -p superset-api-plus down -v

Outra instância: defina SUPERSET_URL, SUPERSET_USERNAME, SUPERSET_PASSWORD e, para os testes que
registram um database, SUPERSET_TEST_DATABASE_URI (URI vista pelo servidor Superset).

Os testes criam seus próprios objetos (prefixo "zz-superset-api-plus-teste") e os removem ao final.
"""
import importlib
import os
import uuid
import zipfile

import pytest

from supersetapiplus.base.datasource import DataSource
from supersetapiplus.charts.charts import Chart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.databases import Database
from supersetapiplus.datasets import Dataset
from supersetapiplus.exceptions import BadRequestError, NotFound
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.saved_queries import SavedQuery


def config(nome: str, alternativa: str | None = None, padrao: str | None = None) -> str | None:
    return os.getenv(nome) or (os.getenv(alternativa) if alternativa else None) or padrao


ATIVO = bool(os.getenv("SUPERSET_URL") or os.getenv("SUPERSET_INTEGRATION"))
URL = config("SUPERSET_URL", padrao=f"http://127.0.0.1:{os.getenv('SUPERSET_TEST_PORT', '8089')}")
USUARIO = config("SUPERSET_USERNAME", "SUPERSET_ADMIN_USERNAME")
SENHA = config("SUPERSET_PASSWORD", "SUPERSET_ADMIN_PASSWORD")
DATABASE_URI = config("SUPERSET_TEST_DATABASE_URI") or (
    "postgresql://{u}:{p}@pg:5432/{d}".format(u=os.getenv("POSTGRES_USER"), p=os.getenv("POSTGRES_PASSWORD"),
                                             d=os.getenv("POSTGRES_DB", "testes"))
    if os.getenv("POSTGRES_USER") and os.getenv("POSTGRES_PASSWORD") else None)

pytestmark = pytest.mark.skipif(not (ATIVO and USUARIO and SENHA),
                                reason="defina SUPERSET_INTEGRATION=1 (stack de testes) ou SUPERSET_URL e credenciais")

PREFIXO = "zz-superset-api-plus-teste"
SQL_DATASET = "select 'Natal' as campus, 10 as total union all select 'Mossoró', 7"


def nome(sufixo: str) -> str:
    return f"{PREFIXO}-{sufixo}-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def client():
    client = SupersetClient(URL, USUARIO, SENHA, verify=URL.startswith("https"))
    client.enable_session_mode()
    return client


@pytest.fixture(scope="module")
def database(client):
    if not DATABASE_URI:
        pytest.skip("defina SUPERSET_TEST_DATABASE_URI ou POSTGRES_USER/POSTGRES_PASSWORD da stack")
    db = Database(database_name=nome("db"), sqlalchemy_uri=DATABASE_URI, expose_in_sqllab=True)
    client.databases.add(db)
    yield db
    client.databases.delete(db.id)


@pytest.fixture(scope="module")
def dataset(client, database):
    ds = Dataset(table_name=nome("ds"), schema="public", sql=SQL_DATASET, database_id=database.id)
    client.datasets.add(ds)
    yield ds
    client.datasets.delete(ds.id)


def novo_grafico(viz_type: str, dataset: Dataset) -> Chart:
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    chart = Chart.get_class(viz_type, f"supersetapiplus.charts.{viz_type}").instance(
        slice_name=nome(viz_type), datasource=DataSource(id=dataset.id, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    return chart


# --- Autenticação e leitura ----------------------------------------------------------------

def test_sessao_autentica_e_lista(client):
    assert client.charts.count() >= 0
    assert client.dashboards.count() >= 0


def test_find_one_sem_resultado_levanta_not_found(client):
    filtro = QueryStringFilter()
    filtro.add("slice_name", QueryOperator.EQUAL, nome("inexistente"))

    with pytest.raises(NotFound):
        client.charts.find_one(filtro)


# --- Database, dataset e consulta salva ----------------------------------------------------

def test_database_criado_e_lido(client, database):
    lido = client.databases.get(database.id)

    assert lido.database_name == database.database_name


def test_database_com_uri_invalida_e_recusado(client):
    with pytest.raises(BadRequestError):
        client.databases.add(Database(database_name=nome("db-invalido"), sqlalchemy_uri="nao-e-uma-uri"))


def test_dataset_criado_alterado_e_lido(client, dataset):
    lido = client.datasets.get(dataset.id)
    lido.description = "alterado pelos testes"
    lido.save()

    assert client.datasets.get(dataset.id).description == "alterado pelos testes"


def test_consulta_salva_criada_e_removida(client, database):
    consulta = SavedQuery(label=nome("sq"), sql="select 1", db_id=database.id, schema="public")

    client.saved_queries.add(consulta)
    try:
        assert client.saved_queries.get(consulta.id).label == consulta.label
    finally:
        assert client.saved_queries.delete(consulta.id)


# --- Gráficos e dashboard ------------------------------------------------------------------

@pytest.mark.parametrize("viz_type", ["table", "pie"])
def test_grafico_criado_por_codigo_faz_ida_e_volta(client, dataset, viz_type):
    chart = novo_grafico(viz_type, dataset)

    client.charts.add(chart)
    try:
        lido = client.charts.get(chart.id)
        assert str(lido.viz_type) == viz_type
        assert lido.datasource_id == dataset.id
        assert lido.params.to_dict() == chart.params.to_dict()

        lido.slice_name = f"{chart.slice_name}-alterado"
        lido.save()
        assert client.charts.get(chart.id).slice_name.endswith("-alterado")
    finally:
        assert client.charts.delete(chart.id)


def test_dashboard_criado_alterado_e_removido(client):
    dashboard = Dashboard(dashboard_title=nome("dash"))

    client.dashboards.add(dashboard)
    try:
        lido = client.dashboards.get(dashboard.id)
        lido.dashboard_title = f"{dashboard.dashboard_title}-alterado"
        lido.save()
        assert client.dashboards.get(dashboard.id).dashboard_title.endswith("-alterado")
    finally:
        assert client.dashboards.delete(dashboard.id)


def test_exporta_grafico_em_zip(client, dataset, tmp_path):
    chart = novo_grafico("table", dataset)
    client.charts.add(chart)
    try:
        destino = tmp_path / "chart.zip"
        client.charts.export([chart.id], destino)

        with zipfile.ZipFile(destino) as arquivo:
            assert any(n.endswith(".yaml") and "/charts/" in n for n in arquivo.namelist())
    finally:
        client.charts.delete(chart.id)


# --- SQL Lab -------------------------------------------------------------------------------

def test_executa_sql_pelo_database(client, database):
    colunas, dados = client.databases.get(database.id).run("select 1 as um")

    assert dados == [{"um": 1}]


# --- Filtros de listagem ---------------------------------------------------------------------

def test_operadores_da_lib_sao_aceitos_pelo_servidor(client):
    filtros = client.get(client.join_urls(client.charts.base_url, "_info"), params={"q": "(keys:!(filters))"}).json()
    aceitos = {op["operator"] for coluna in filtros["filters"].values() for op in coluna}

    assert {op.value for op in QueryOperator} <= aceitos


@pytest.mark.parametrize("operador,valor", [(QueryOperator.NOT_EQUAL, "x"), (QueryOperator.CONTAINS, "zz"),
                                            (QueryOperator.STARTS_WITH, "zz"), (QueryOperator.IN, ["table"])])
def test_listagem_com_operadores_responde_sem_erro(client, operador, valor):
    filtro = QueryStringFilter()
    filtro.add("viz_type" if operador in (QueryOperator.IN, QueryOperator.NOT_EQUAL) else "slice_name", operador, valor)

    assert client.charts.count(filtro) >= 0


def test_grafico_e_associado_ao_dashboard_pelo_layout(client, dataset):
    chart = novo_grafico("table", dataset)
    client.charts.add(chart)
    dashboard = Dashboard(dashboard_title=nome("dash-assoc"))
    client.dashboards.add(dashboard)
    try:
        dashboard.position.add_chart(chart, chart.slice_name, parent=dashboard.position.add_tab("Aba"))
        dashboard.save()
        client.dashboards.attach_charts(dashboard)

        assert [c.id for c in client.dashboards.get(dashboard.id).get_charts()] == [chart.id]
        assert client.charts.dashboard_ids(chart.id) == [dashboard.id]
    finally:
        client.dashboards.delete(dashboard.id)
        client.charts.delete(chart.id)

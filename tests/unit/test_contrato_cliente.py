"""Contrato público do cliente: autenticação, busca, leitura e gravação via API REST.

Rede de proteção para a reorganização de pacotes (T13): os testes exercitam só a API
pública (inclusive a usada pelo adaptador do bi_cpa) e verificam as requisições que chegam
ao Superset, sem depender da implementação interna. Payloads sintéticos.
"""
import json
from urllib.parse import parse_qs, urlparse

import importlib

import pytest
import requests
import requests_mock as rm

from supersetapiplus.charts.charts import Chart
from supersetapiplus import client as client_module
from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import MultipleFound, NotFound, UnsupportedTypeError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

HOST = "https://superset.exemplo"
API = f"{HOST}/api/v1"
TOKEN = "jwt-de-teste"

# /_info real do Superset 6.1.0 para charts: o ChartRestApi declara add/edit_columns = ["slice_name"],
# mas valida o corpo com ChartPostSchema/ChartPutSchema. Por isso o /_info não serve de filtro.
CHART_INFO = {"add_columns": [{"name": "slice_name"}], "edit_columns": [{"name": "slice_name"}]}

# Campos aceitos pelos schemas do Superset 6.1.0 (OpenAPI: ChartRestApi.post / ChartRestApi.put).
CHART_POST_ACEITOS = {"cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
                      "datasource_name", "datasource_type", "description", "external_url", "is_managed_externally",
                      "owners", "params", "query_context", "query_context_generation", "slice_name", "viz_type"}
CHART_POST_OBRIGATORIOS = {"datasource_id", "datasource_type", "slice_name"}
CHART_PUT_ACEITOS = (CHART_POST_ACEITOS - {"datasource_name"}) | {"tags"}


def chart_payload(chart_id: int, viz_type: str = "table", slice_name: str = "Respondentes por campus") -> dict:
    params = {"datasource": "1__table", "viz_type": viz_type, "query_mode": "aggregate",
              "groupby": ["campus"], "metrics": ["count"], "row_limit": 100}
    return {"id": chart_id, "slice_name": slice_name, "viz_type": viz_type,
            "params": json.dumps(params), "query_context": None}


def query_param(request) -> dict:
    return json.loads(parse_qs(urlparse(request.url).query)["q"][0])


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": TOKEN, "refresh_token": "r"})
        m.get(f"{API}/chart/_info", json=CHART_INFO)
        m.get(f"{API}/security/csrf_token/", json={"result": "csrf-api"})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robo", "senha", verify=True)


def filtro(column: str, value) -> QueryStringFilter:
    f = QueryStringFilter()
    f.add(column, QueryOperator.EQUAL, value)
    return f


# --- Autenticação --------------------------------------------------------------------------

def test_login_jwt_envia_credenciais_e_usa_bearer_nas_chamadas(client, mock):
    mock.get(f"{API}/chart/", json={"count": 3, "result": []})

    assert client.charts.count() == 3

    login = next(r for r in mock.request_history if r.path.endswith("/security/login"))
    assert login.json() == {"username": "robo", "password": "senha", "provider": "db", "refresh": True}
    assert mock.last_request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert mock.last_request.headers["X-CSRFToken"] == "csrf-api"


def test_modo_sessao_faz_login_por_formulario_com_csrf_na_mesma_sessao(mock, monkeypatch):
    # O requests_mock não grava cookies de resposta no jar da sessão; os callbacks fazem o papel
    # do Superset, emitindo o cookie na sessão criada pelo cliente.
    sessoes = []

    class SessaoCapturada(requests.Session):
        def __init__(self):
            super().__init__()
            sessoes.append(self)

    def emite_cookie(valor):
        def callback(request, context):
            sessoes[-1].cookies.set("session", valor, domain="superset.exemplo", path="/")
            return '<form><input name="csrf_token" value="csrf-form"></form>'
        return callback

    monkeypatch.setattr(client_module.requests, "Session", SessaoCapturada)
    mock.get(f"{HOST}/login/", text=emite_cookie("pre-login"))
    mock.post(f"{HOST}/login/", text=emite_cookie("autenticado"))
    mock.get(f"{API}/chart/", json={"count": 0, "result": []})
    client = SupersetClient(HOST, "robo", "senha", verify=True)

    client.enable_session_mode()
    client.charts.count()
    mock.delete(f"{API}/chart/9", json={"message": "OK"})
    client.charts.delete(9)

    get_login, post_login = [r for r in mock.request_history if r.path == "/login/"]
    assert parse_qs(post_login.text) == {"username": ["robo"], "password": ["senha"], "csrf_token": ["csrf-form"]}
    assert "session=pre-login" in post_login.headers["Cookie"]
    assert "session=autenticado" in mock.last_request.headers["Cookie"]
    assert "Authorization" not in mock.last_request.headers
    assert not any(r.path.endswith("/security/login") for r in mock.request_history)
    # Escrita com cookie exige o token CSRF ("The CSRF token is missing." no Superset 6.1.0).
    assert mock.last_request.method == "DELETE"
    assert mock.last_request.headers["X-CSRFToken"] == "csrf-api"
    assert mock.last_request.headers["Referer"] == f"{HOST}/"


# --- Busca e leitura -----------------------------------------------------------------------

def test_find_envia_filtros_paginacao_e_devolve_graficos_tipados(client, mock):
    mock.get(f"{API}/chart/", json={"count": 1, "result": [chart_payload(10)]})

    charts = client.charts.find(filtro("slice_name", "Respondentes por campus"), page_size=50, page=2)

    assert query_param(mock.last_request) == {
        "page_size": 50, "page": 2, "columns": [],
        "filters": [{"col": "slice_name", "opr": "eq", "value": "Respondentes por campus"}],
    }
    assert [type(c).__name__ for c in charts] == ["TableChart"]
    assert isinstance(charts[0], Chart) and charts[0].id == 10


def test_find_com_colunas_restritas_devolve_objetos_parciais(client, mock):
    # A listagem só traz as colunas pedidas (sem params); o objeto parcial serve para obter o id.
    mock.get(f"{API}/chart/", json={"count": 1, "result": [{"id": 10, "slice_name": "x", "viz_type": "table"}]})

    charts = client.charts.find(filtro("slice_name", "x"), columns=["id", "slice_name", "viz_type"])

    assert query_param(mock.last_request)["columns"] == ["id", "slice_name", "viz_type"]
    assert [c.id for c in charts] == [10]


def test_find_one_sem_resultado_levanta_not_found(client, mock):
    mock.get(f"{API}/chart/", json={"count": 0, "result": []})

    with pytest.raises(NotFound):
        client.charts.find_one(filtro("slice_name", "inexistente"))


def test_find_one_com_varios_resultados_levanta_multiple_found(client, mock):
    mock.get(f"{API}/chart/", json={"count": 2, "result": [chart_payload(1), chart_payload(2)]})

    with pytest.raises(MultipleFound):
        client.charts.find_one(filtro("viz_type", "table"))


def test_find_one_full_recarrega_o_grafico_pelo_id(client, mock):
    mock.get(f"{API}/chart/", json={"count": 1, "result": [{"id": 10, "slice_name": "x", "viz_type": "table"}]})
    mock.get(f"{API}/chart/10", json={"id": 10, "result": chart_payload(10)})

    chart = client.charts.find_one(filtro("slice_name", "x"), full=True)

    assert mock.last_request.path == "/api/v1/chart/10"
    assert chart.slice_name == "Respondentes por campus"
    assert chart.params.groupby == ["campus"]


def test_get_resolve_a_classe_pelo_viz_type(client, mock):
    mock.get(f"{API}/chart/7", json={"id": 7, "result": chart_payload(7, viz_type="pie")})

    chart = client.charts.get(7)

    assert type(chart).__name__ == "PieChart" and chart.id == 7


def test_get_de_viz_type_sem_modelo_levanta_unsupported_type(client, mock):
    mock.get(f"{API}/chart/8", json={"id": 8, "result": chart_payload(8, viz_type="histogram_v2")})

    with pytest.raises(UnsupportedTypeError):
        client.charts.get(8)


def test_get_class_do_chart_resolve_pelo_viz_type():
    # Contrato atual: o módulo do tipo precisa estar importado (o registro explícito da T7 remove essa exigência).
    importlib.import_module("supersetapiplus.charts.table")
    assert Chart.get_class("table", "supersetapiplus.charts.table").__name__ == "TableChart"


# --- Gravação ------------------------------------------------------------------------------

def test_add_envia_campos_aceitos_e_obrigatorios_do_schema_e_guarda_o_id(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_payload(9)})
    mock.post(f"{API}/chart/", json={"id": 99, "result": {}})
    chart = client.charts.get(9)

    novo_id = client.charts.add(chart)

    payload = mock.last_request.json()
    assert novo_id == 99 and chart.id == 99
    assert "id" not in payload
    assert set(payload) <= CHART_POST_ACEITOS
    assert CHART_POST_OBRIGATORIOS <= set(payload)
    assert payload["datasource_id"] == 1 and payload["datasource_type"] == "table"
    assert json.loads(payload["params"])["groupby"] == ["campus"]


def test_save_faz_put_no_proprio_id_com_campos_aceitos_pelo_schema(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_payload(9)})
    mock.put(f"{API}/chart/9", json={"id": 9, "result": {}})
    chart = client.charts.get(9)
    chart.slice_name = "Novo título"

    chart.save()

    assert mock.last_request.method == "PUT" and mock.last_request.path == "/api/v1/chart/9"
    payload = mock.last_request.json()
    assert payload["slice_name"] == "Novo título"
    assert set(payload) <= CHART_PUT_ACEITOS
    assert json.loads(payload["params"])["groupby"] == ["campus"]


def test_delete_devolve_true_quando_o_superset_confirma(client, mock):
    mock.delete(f"{API}/chart/9", json={"message": "OK"})

    assert client.charts.delete(9) is True


DASHBOARD_ACEITOS = {"certification_details", "certified_by", "css", "dashboard_title", "external_url",
                     "is_managed_externally", "json_metadata", "owners", "position_json", "published", "roles", "slug"}


def test_add_de_dashboard_envia_so_campos_aceitos_pelo_schema(client, mock):
    from supersetapiplus.dashboards.dashboards import Dashboard

    mock.get(f"{API}/dashboard/_info", json={"add_columns": [{"name": "dashboard_title"}]})
    mock.post(f"{API}/dashboard/", json={"id": 5, "result": {}})

    assert client.dashboards.add(Dashboard(dashboard_title="Painel")) == 5

    payload = mock.last_request.json()
    assert payload["dashboard_title"] == "Painel"
    assert set(payload) <= DASHBOARD_ACEITOS
    assert isinstance(payload["json_metadata"], str) and isinstance(payload["position_json"], str)


def test_find_nao_quebra_a_listagem_por_item_de_tipo_sem_modelo(client, mock):
    from supersetapiplus.base.base import UnsupportedObject

    mock.get(f"{API}/chart/", json={"count": 2, "result": [
        {"id": 1, "slice_name": "a", "viz_type": "table"},
        {"id": 2, "slice_name": "b", "viz_type": "echarts_timeseries_line"},
    ]})

    charts = client.charts.find(QueryStringFilter(), columns=["id", "slice_name", "viz_type"])

    assert [c.id for c in charts] == [1, 2]
    assert type(charts[0]).__name__ == "TableChart"
    assert isinstance(charts[1], UnsupportedObject) and charts[1].viz_type == "echarts_timeseries_line"

"""Camada HTTP: retry, erros por status, renovação do JWT, multipart, SQL Lab, busca e contagem."""
import json
import zipfile
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import requests_mock as rm

from supersetapiplus.client import SupersetClient
from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    NotFound,
    QueryLimitReached,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.utils.request_handler import IDEMPOTENT_METHODS, RequestHandler

HOST = "https://superset.exemplo"
API = f"{HOST}/api/v1"


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "acesso-1", "refresh_token": "renovacao"})
        m.get(f"{API}/security/csrf_token/", json={"result": "csrf"})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robo", "senha")


def query_param(request) -> dict:
    return json.loads(parse_qs(urlparse(request.url).query)["q"][0])


# --- Retry -----------------------------------------------------------------------------------

def test_retry_so_em_metodos_idempotentes_e_sem_engolir_o_erro_da_api():
    session = requests.Session()

    RequestHandler.configure_retries(session, retries=3, backoff_factor=0.1)

    retry = session.get_adapter("https://x").max_retries
    assert "POST" not in retry.allowed_methods and set(retry.allowed_methods) == IDEMPOTENT_METHODS
    assert retry.total == 3 and 429 in retry.status_forcelist and 503 in retry.status_forcelist
    assert retry.raise_on_status is False and retry.respect_retry_after_header is True


def test_adapter_de_retry_e_montado_uma_vez_por_sessao():
    session = requests.Session()
    RequestHandler.configure_retries(session)
    adapter = session.get_adapter("https://x")

    RequestHandler.configure_retries(session)

    assert session.get_adapter("https://x") is adapter


# --- Erros por status ------------------------------------------------------------------------

@pytest.mark.parametrize("status,corpo,excecao", [
    (401, {"msg": "Token has expired"}, UnauthorizedError),
    (403, {"message": "Forbidden"}, ForbiddenError),
    (404, {"message": "Not found"}, ResourceNotFoundError),
    (422, {"message": {"slice_name": ["Missing data for required field."]}}, UnprocessableEntityError),
    (400, {"message": "Bad request"}, BadRequestError),
    (400, {"errors": [{"message": "x", "error_type": "GENERIC"}]}, ComplexBadRequestError),
])
def test_erros_da_api_viram_excecoes_por_status(status, corpo, excecao):
    with rm.Mocker() as m:
        m.get(f"{API}/chart/1", status_code=status, json=corpo)
        with pytest.raises(excecao) as info:
            RequestHandler.request_with_retry(f"{API}/chart/1", retries=0)

    assert info.value.response.status_code == status
    if excecao is UnprocessableEntityError:
        assert info.value.message == corpo["message"]


def test_excecoes_por_status_continuam_sendo_bad_request_error():
    for excecao in (UnauthorizedError, ForbiddenError, ResourceNotFoundError, UnprocessableEntityError):
        assert issubclass(excecao, BadRequestError)


# --- Renovação do JWT ------------------------------------------------------------------------

def test_401_renova_o_jwt_com_o_refresh_token_e_repete_uma_vez(client, mock):
    mock.get(f"{API}/chart/1", [{"status_code": 401, "json": {"msg": "Token has expired"}},
                                {"json": {"id": 1, "result": {}}}])
    mock.post(f"{API}/security/refresh", json={"access_token": "acesso-2"})

    client.get(f"{API}/chart/1")

    refresh = next(r for r in mock.request_history if r.path.endswith("/security/refresh"))
    assert refresh.headers["Authorization"] == "Bearer renovacao"
    assert mock.last_request.headers["Authorization"] == "Bearer acesso-2"


def test_401_no_modo_sessao_nao_tenta_renovar(mock):
    mock.get(f"{HOST}/login/", text='<input name="csrf_token" value="t">')
    mock.post(f"{HOST}/login/", text="ok")
    mock.get(f"{API}/chart/1", status_code=401, json={"msg": "expired"})
    client = SupersetClient(HOST, "robo", "senha")
    sessao = requests.Session()
    sessao.cookies.set("session", "x", domain="superset.exemplo")
    client._session, client._session_mode = sessao, True

    with pytest.raises(UnauthorizedError):
        client.get(f"{API}/chart/1")
    assert not any(r.path.endswith("/security/refresh") for r in mock.request_history)


def test_enable_session_mode_prevalece_mesmo_apos_acesso_a_session(client, mock, monkeypatch):
    jwt_session = client.session
    monkeypatch.setattr(type(client), "enable_session_auth", lambda self, s, u, p: s.cookies.set("session", "c"))

    client.enable_session_mode()

    assert client.session is not jwt_session


# --- Multipart, SQL Lab, busca e contagem ----------------------------------------------------

def test_import_envia_multipart_sem_content_type_json(client, mock, tmp_path):
    arquivo = tmp_path / "graficos.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("export/metadata.yaml", "version: 1.0.0\n")
    mock.get(f"{API}/chart/_info", json={})
    mock.post(f"{API}/chart/import/", json={"message": "OK"})

    assert client.charts.import_file(arquivo, overwrite=True) is True

    pedido = mock.last_request
    assert pedido.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="formData"; filename="graficos.zip"' in pedido.body
    assert b'name="overwrite"' in pedido.body


def test_import_de_assets_abre_o_caminho_informado(client, mock, tmp_path):
    arquivo = tmp_path / "subdir" / "assets.zip"
    arquivo.parent.mkdir()
    arquivo.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    mock.post(f"{API}/assets/import/", json={"message": "OK"})

    assert client.assets.import_file(arquivo) is True
    assert b'filename="assets.zip"' in mock.last_request.body


def test_run_usa_o_sql_lab_da_api(client, mock):
    mock.post(f"{API}/sqllab/execute/", json={"status": "success", "columns": [{"name": "um"}], "data": [{"um": 1}]})

    colunas, dados = client.run(database_id=3, query="select 1 as um", query_limit=10, schema="public")

    assert mock.last_request.json() == {"database_id": 3, "sql": "select 1 as um", "runAsync": False,
                                        "queryLimit": 10, "schema": "public"}
    assert colunas == [{"name": "um"}] and dados == [{"um": 1}]


def test_run_assincrono_e_limite_sao_sinalizados(client, mock):
    mock.post(f"{API}/sqllab/execute/", [{"status_code": 202, "json": {"status": "running"}},
                                          {"json": {"displayLimitReached": True, "columns": [], "data": []}}])

    with pytest.raises(NotImplementedError):
        client.run(database_id=3, query="select 1")
    with pytest.raises(QueryLimitReached):
        client.run(database_id=3, query="select 1")


def test_get_datasource_pelo_nome_da_tabela(client, mock):
    mock.get(f"{API}/dataset/", [{"json": {"count": 1, "result": [{"id": 7, "datasource_type": "table"}]}},
                                 {"json": {"count": 0, "result": []}}])

    datasource = client.datasets.get_datasource("vw_respostas")

    assert (datasource.id, datasource.type) == (7, "table")
    assert query_param(mock.last_request)["filters"] == [{"col": "table_name", "opr": "eq", "value": "vw_respostas"}]
    with pytest.raises(NotFound):
        client.datasets.get_datasource("inexistente")


def test_count_com_filtro_e_find_ordenado(client, mock):
    filtro = QueryStringFilter()
    filtro.add("viz_type", QueryOperator.EQUAL, "pie")
    mock.get(f"{API}/chart/", json={"count": 4, "result": []})

    assert client.charts.count(filtro) == 4
    assert query_param(mock.last_request)["filters"][0]["value"] == "pie"

    client.charts.find(filtro, columns=["id"], order_column="changed_on", order_direction="desc")
    assert query_param(mock.last_request)["order_column"] == "changed_on"
    assert query_param(mock.last_request)["order_direction"] == "desc"


def test_find_all_percorre_as_paginas(client, mock):
    pagina = lambda ids: {"json": {"count": 5, "result": [{"id": i, "viz_type": "table"} for i in ids]}}  # noqa: E731
    mock.get(f"{API}/chart/", [pagina([1, 2]), pagina([3, 4]), pagina([5])])

    charts = client.charts.find_all(columns=["id", "viz_type"], page_size=2)

    assert [c.id for c in charts] == [1, 2, 3, 4, 5]
    assert [query_param(r)["page"] for r in mock.request_history if r.path == "/api/v1/chart/"] == [0, 1, 2]

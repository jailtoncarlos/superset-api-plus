"""Segurança do cliente: logging da aplicação, verificação TLS e segredos fora dos logs."""
import json
import logging
import subprocess
import sys

import pytest
import requests
import requests_mock

from supersetapiplus.client import SupersetClient
from supersetapiplus.utils.request_handler import RequestHandler
from supersetapiplus.utils.sensitive import MASK, mask_body, mask_data, mask_headers

HOST = "https://superset.exemplo"
SENHA = "s3nh4-ultrasecreta"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.token-de-acesso"


def client_com_sessao(verify: bool) -> SupersetClient:
    client = SupersetClient(HOST, username="robo", password=SENHA, verify=verify)
    client._session = requests.Session()  # evita o login real
    return client


def test_importar_o_pacote_nao_configura_o_logging_da_aplicacao():
    codigo = "import logging, supersetapiplus; print(len(logging.getLogger().handlers))"
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True)

    assert saida.stdout.strip() == "0"


@pytest.mark.parametrize("verify", [True, False])
@pytest.mark.parametrize("metodo", ["get", "post", "put", "delete"])
def test_metodos_http_do_cliente_respeitam_verify(metodo, verify):
    client = client_com_sessao(verify)
    url = f"{HOST}/api/v1/chart/1"

    with requests_mock.Mocker() as mock:
        getattr(mock, metodo)(url, json={"result": {}})
        getattr(client, metodo)(url)

    assert mock.last_request.verify is verify


def test_request_sem_verify_explicito_herda_a_sessao():
    session = requests.Session()
    session.verify = True

    with requests_mock.Mocker() as mock:
        mock.get(f"{HOST}/api/v1/me/", json={})
        RequestHandler.request_with_retry(f"{HOST}/api/v1/me/", session=session)

    assert mock.last_request.verify is True


def test_log_de_erro_http_nao_expoe_senha_token_nem_cookie(caplog):
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {TOKEN}", "X-CSRFToken": "csrf-123"})
    session.cookies.set("session", "cookie-de-sessao")

    with requests_mock.Mocker() as mock, caplog.at_level(logging.DEBUG):
        mock.post(f"{HOST}/api/v1/security/login", status_code=401,
                  json={"message": "Not authorized", "access_token": TOKEN},
                  headers={"Set-Cookie": "session=cookie-de-sessao"})
        with pytest.raises(requests.HTTPError):
            RequestHandler.request_with_retry(
                f"{HOST}/api/v1/security/login", method="POST", session=session, retries=0,
                json={"username": "robo", "password": SENHA, "provider": "db"},
            )

    assert caplog.text
    for segredo in (SENHA, TOKEN, "csrf-123", "cookie-de-sessao"):
        assert segredo not in caplog.text, segredo


def test_mascara_cabecalhos_sensiveis_sem_alterar_os_demais():
    headers = {"Authorization": "Bearer x", "Cookie": "a=b", "X-CSRFToken": "c", "Accept": "application/json"}

    assert mask_headers(headers) == {"Authorization": MASK, "Cookie": MASK, "X-CSRFToken": MASK,
                                     "Accept": "application/json"}
    assert headers["Authorization"] == "Bearer x"


def test_mascara_corpo_json_form_e_uri_de_conexao():
    corpo_json = json.dumps({"username": "robo", "password": SENHA, "nested": {"refresh_token": "r"}})
    corpo_form = f"csrf_token=abc&username=robo&password={SENHA}"
    database = {"database_name": "dw", "sqlalchemy_uri": f"postgresql://robo:{SENHA}@db:5432/dw"}

    assert json.loads(mask_body(corpo_json)) == {"username": "robo", "password": MASK, "nested": {"refresh_token": MASK}}
    assert mask_body(corpo_form) == f"csrf_token={MASK.replace('*', '%2A')}&username=robo&password={MASK.replace('*', '%2A')}"
    assert mask_data(database)["sqlalchemy_uri"] == f"postgresql://robo:{MASK}@db:5432/dw"

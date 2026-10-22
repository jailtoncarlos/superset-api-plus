"""Fixtures compartilhadas e configuração dos testes de integração."""
import json
import os
from pathlib import Path

import pytest
import requests_mock  # noqa

from supersetapiplus.client import SupersetClient

RAIZ = Path(__file__).parent.parent
API_MOCKS = Path(__file__).parent / "mocks" / "endpoints"

# Endereço fictício usado só pelos mocks HTTP.
SUPERSET_BASE_URI = "https://superset.mock"
SUPERSET_API_URI = f"{SUPERSET_BASE_URI}/api/v1"


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    """Carrega o .env da stack de testes no ambiente, sem sobrescrever variáveis já definidas."""
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            nome, valor = linha.split("=", 1)
            os.environ.setdefault(nome.strip(), valor.strip().strip("\"'"))


carregar_env()


@pytest.fixture
def permanent_requests(requests_mock):  # noqa
    # Registra cada arquivo de tests/mocks/endpoints/<recurso>/<endpoint>.<método> como resposta.
    for domain in API_MOCKS.iterdir():
        if domain.is_dir():
            for endpoint in domain.iterdir():
                if endpoint.is_file():
                    endpoint_name, action = endpoint.name.split(".")
                    url = f"{SUPERSET_API_URI}/{domain.name}/{endpoint_name}"
                    getattr(requests_mock, action)(url=url, json=json.load(endpoint.open()))
                    getattr(requests_mock, action)(url=f"{url}/", json=json.load(endpoint.open()))


@pytest.fixture
def client(permanent_requests):
    yield SupersetClient(SUPERSET_BASE_URI, "test", "test")

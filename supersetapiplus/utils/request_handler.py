"""Transporte HTTP do cliente: retry, timeouts, mapeamento de erros e logs mascarados."""
import logging
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from supersetapiplus.utils.sensitive import mask_body, mask_headers, mask_request_kwargs

logger = logging.getLogger(__name__)


def _numero_do_ambiente(nome: str, padrao: float) -> float:
    """Lê um parâmetro de rede do ambiente (ex.: SUPERSET_API_PLUS_TIMEOUT_READ=60), com valor padrão."""
    valor = os.getenv(nome)
    if valor is None or not valor.strip():
        return padrao
    try:
        return type(padrao)(valor)
    except ValueError as err:
        raise ValueError(f"{nome}={valor!r} não é um número válido") from err


# Padrões de rede, ajustáveis por variável de ambiente sem alterar código; cada chamada ainda
# aceita timeout_connect/timeout_read/retries/backoff_factor explícitos.
TIMEOUT_CONNECT = _numero_do_ambiente("SUPERSET_API_PLUS_TIMEOUT_CONNECT", 10)
TIMEOUT_READ = _numero_do_ambiente("SUPERSET_API_PLUS_TIMEOUT_READ", 20)
DEFAULT_RETRIES = _numero_do_ambiente("SUPERSET_API_PLUS_RETRIES", 3)
DEFAULT_BACKOFF_FACTOR = _numero_do_ambiente("SUPERSET_API_PLUS_BACKOFF_FACTOR", 0.5)

# Falhas transitórias que justificam nova tentativa (429 respeita o cabeçalho Retry-After).
DEFAULT_STATUS_FORCELIST = (429, 500, 502, 503, 504)

# Só métodos idempotentes são repetidos: repetir um POST que falhou no servidor pode criar o
# recurso em duplicidade.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})

HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})

STATUS_EXCEPTIONS = {
    401: UnauthorizedError,
    403: ForbiddenError,
    404: ResourceNotFoundError,
    422: UnprocessableEntityError,
}


class RequestHandler:
    """Executa as requisições HTTP da biblioteca sobre uma `requests.Session`."""

    @staticmethod
    def configure_retries(session: requests.Session, retries: int = DEFAULT_RETRIES,
                          backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
                          status_forcelist=DEFAULT_STATUS_FORCELIST) -> None:
        """Monta na sessão o adapter com retry, uma vez por configuração (reaproveita o pool de conexões)."""
        config = (int(retries), float(backoff_factor), tuple(status_forcelist))
        if getattr(session, "_supersetapiplus_retry", None) == config:
            return
        retry = Retry(
            total=config[0],
            backoff_factor=config[1],
            status_forcelist=config[2],
            allowed_methods=IDEMPOTENT_METHODS,
            respect_retry_after_header=True,
            # Esgotadas as tentativas, devolve a última resposta para que raise_for_status
            # converta o erro do Superset (antes era um RetryError sem a mensagem da API).
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session._supersetapiplus_retry = config

    @classmethod
    def request_with_retry(cls, url: str, method: str = "GET", session: requests.Session | None = None,
                           **kwargs) -> requests.Response:
        """
        Realiza uma requisição HTTP com retry em falhas transitórias e converte erros da API.

        Args:
            url: URL da requisição.
            method: "GET", "POST", "PUT" ou "DELETE".
            session: sessão autenticada; sem ela, usa uma sessão nova sem estado.
            **kwargs: headers, params, data, json, files, verify (None herda session.verify), stream,
                timeout_connect, timeout_read, retries, backoff_factor, status_forcelist.

        Raises:
            UnauthorizedError, ForbiddenError, ResourceNotFoundError, UnprocessableEntityError,
            BadRequestError, ComplexBadRequestError: respostas de erro do Superset.
            requests.RequestException: falhas de conexão e timeout.
        """
        method = method.upper()
        if method not in HTTP_METHODS:
            raise ValueError(f"Método HTTP inválido: {method}. Use {', '.join(sorted(HTTP_METHODS))}.")

        session = session or requests.Session()
        cls.configure_retries(
            session,
            retries=kwargs.get("retries", DEFAULT_RETRIES),
            backoff_factor=kwargs.get("backoff_factor", DEFAULT_BACKOFF_FACTOR),
            status_forcelist=kwargs.get("status_forcelist", DEFAULT_STATUS_FORCELIST),
        )

        logger.debug("Realizando %s em %s ... kwargs: %s ...", method, url, mask_request_kwargs(kwargs))
        try:
            response = session.request(
                method,
                url,
                headers=kwargs.get("headers"),
                params=kwargs.get("params"),
                data=kwargs.get("data"),
                json=kwargs.get("json"),
                files=kwargs.get("files"),
                # None herda o `session.verify` (padrão True no requests).
                verify=kwargs.get("verify"),
                stream=kwargs.get("stream", False),
                timeout=(kwargs.get("timeout_connect", TIMEOUT_CONNECT), kwargs.get("timeout_read", TIMEOUT_READ)),
            )
        except requests.exceptions.RequestException as err:
            logger.error("Falha de rede em %s %s: %s", method, url, err)
            raise

        cls.raise_for_status(response)
        logger.debug("Request %s to %s successful!", method, url)
        return response

    @classmethod
    def raise_for_status(cls, response: requests.Response) -> None:
        """
        Converte respostas de erro em exceções da biblioteca, com log mascarado.

        - corpo com `errors` (lista de erros do Superset): ComplexBadRequestError;
        - 401/403/404/422: exceção específica (subclasses de BadRequestError), com `message`
          (no 422, o dict de erros por campo);
        - demais status com `message`: BadRequestError; sem corpo reconhecível: requests.HTTPError.
        """
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            request = response.request
            cls._log_error(request, response)

            try:
                body = response.json()
            except ValueError:
                body = None
            errors = body.get("errors") if isinstance(body, dict) else None
            message = body.get("message") if isinstance(body, dict) else None

            if errors:
                raise ComplexBadRequestError(*e.args, request=request, response=response, errors=errors) from None
            exception_class = STATUS_EXCEPTIONS.get(response.status_code)
            if exception_class or message:
                raise (exception_class or BadRequestError)(*e.args, request=request, response=response,
                                                           message=message) from None
            raise

    @staticmethod
    def _log_error(request, response) -> None:
        # Cabeçalhos e corpos mascarados: incluem Authorization, cookies, token CSRF e,
        # num login recusado, a senha.
        request_headers = "\n".join(f"{k}: {v}" for k, v in mask_headers(request.headers).items())
        response_headers = "\n".join(f"{k}: {v}" for k, v in mask_headers(response.headers).items())
        try:
            response_body = mask_body(response.text)
        except Exception:
            response_body = "<não foi possível decodificar o corpo da resposta>"
        logger.error(
            "Erro na requisição HTTP\nRequest URL: %s\nRequest Method: %s\nRequest Headers:\n%s\n"
            "Request Body:\n%s\nResponse Status Code: %s\nResponse Headers:\n%s\nResponse Body:\n%s",
            request.url, request.method, request_headers, mask_body(request.body) or "<vazio>",
            response.status_code, response_headers, response_body,
        )

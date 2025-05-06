import logging

import requests
from bs4 import BeautifulSoup

from supersetapiplus.utils.request_handler import RequestHandler

logger = logging.getLogger(__name__)


class SessionAuthMixin:
    """
    Mixin para autenticação baseada em sessão (via cookie 'session') usando o formulário de login do Superset.

    Esta abordagem é necessária para acessar endpoints como `/api/v1/me/` que exigem autenticação baseada em sessão
    e não funcionam apenas com JWT.
    """

    def enable_session_auth(self, session: requests.Session, username: str, password: str) -> None:
        """
        Realiza autenticação via sessão (cookie) no Superset. Após sucesso, o cookie `session` é armazenado na sessão.

        Args:
            session (requests.Session): Sessão de requisições.
            username (str): Nome de usuário do Superset.
            password (str): Senha do usuário.
        """
        login_page_url = f"{self.host}/login/"
        logger.debug(f"[SessionAuth] Requisitando página de login para obter CSRF: {login_page_url}")

        # Etapa 1: Obter o token CSRF da página de login
        resp = RequestHandler.request_with_retry(
            url=login_page_url,
            method="GET",
            verify=self._verify,
            stream=False,
            headers={"Accept": "text/html"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_token_input = soup.find("input", {"name": "csrf_token"})
        if not csrf_token_input or not csrf_token_input.get("value"):
            raise RuntimeError("CSRF token não encontrado no formulário de login.")
        csrf_token = csrf_token_input["value"]
        logger.debug(f"[SessionAuth] Token CSRF extraído: {csrf_token}")

        # Etapa 2: Autenticar com credenciais e CSRF token
        login_data = {
            "username": username,
            "password": password,
            "csrf_token": csrf_token,
        }
        login_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": login_page_url,
        }

        # Realiza POST com sessão externa fornecida (não usada diretamente em RequestHandler)
        response = session.post(
            login_page_url,
            data=login_data,
            headers=login_headers,
            verify=self._verify,
        )
        RequestHandler.raise_for_status(response)

        # Etapa 3: Verificação de sucesso
        if "session" not in session.cookies:
            raise RuntimeError("Autenticação por sessão falhou: cookie 'session' não encontrado.")

        logger.info("[SessionAuth] Autenticação por sessão realizada com sucesso.")

import logging
from typing import runtime_checkable, Protocol
import requests

from supersetapiplus.utils.request_handler import RequestHandler

logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsCSRFToken(Protocol):
    base_url: str  # Assuming base_url is also required
    _csrf_token: str

    def _init_session(self):
        ...

    def get_domain(self) -> str:
        ...  # Ellipsis indicates abstract method

    def join_urls(self, *args: str) -> str:
        ...  # Variadic arguments need to be typed



class CSRFSupportMixin:
    """
    Mixin para fornecer suporte a CSRF em clientes Superset que interagem com rotas não-API.

    Deve ser utilizado apenas em chamadas como /superset/explore/ que exigem proteção CSRF.
    """

    @property
    def csrf_token(self):
        """Returns JWT token via login endpoint."""
        if self._csrf_token is None:
            self._init_session()
        return self._csrf_token

    def enable_csrf(self: SupportsCSRFToken,
                    session: requests.Session, access_token: str, verify: bool = True):
        """
        Adiciona cabeçalhos CSRF e Referer à sessão autenticada.

        Args:
            session (requests.Session): Sessão autenticada com headers JWT.
        """
        csrf_url = self.join_urls(self.base_url, "security/csrf_token/")
        logger.debug(f"Fetching CSRF token in: {csrf_url}")

        # 2. Obtenção do CSRF token
        csrf_resp = RequestHandler.request_with_retry(
            url=csrf_url,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
            verify=verify,
            session=session
        )

        self._csrf_token = csrf_resp.json()["result"]
        logger.debug(f"[OK] CSRF token successfully obtained: {self._csrf_token[:30]}...")
        if self._csrf_token:
            # Definição do cookie necessário para Superset aceitar CSRF
            # session.cookies.set("csrf_access_token", self._csrf_token, domain=self.get_domain())

            session.headers["X-CSRFToken"] = self._csrf_token
            logger.debug(f"CSRF token set successfully:: {self._csrf_token}")
        else:
            logger.warning("CSRF token not found in response.")

import logging
from typing import Any, Protocol, runtime_checkable

import requests

from supersetapiplus.transport.http import RequestHandler

logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsCSRFToken(Protocol):
    """What CSRFSupportMixin needs from the client class it is mixed into."""
    host: str
    _csrf_token: str | None

    def _init_session(self) -> None:
        ...

    @property
    def base_url(self) -> str:
        ...

    def get_domain(self) -> str | None:
        ...  # Ellipsis indicates abstract method

    def join_urls(self, *args: Any) -> str:
        ...  # Variadic arguments need to be typed



class CSRFSupportMixin:
    """
    Mixin that provides CSRF support to Superset clients that interact with non-API routes.

    Should only be used for calls such as /superset/explore/ that require CSRF protection.
    """

    @property
    def csrf_token(self: SupportsCSRFToken) -> str | None:
        """CSRF token of the authenticated session (fetched from /security/csrf_token/ on first use)."""
        if self._csrf_token is None:
            self._init_session()
        return self._csrf_token

    def enable_csrf(self: SupportsCSRFToken,
                    session: requests.Session, access_token: str | None = None, verify: bool = True) -> None:
        """
        Adds CSRF and Referer headers to the authenticated session.

        Args:
            session (requests.Session): Authenticated session (JWT or form-login cookie).
            access_token (str, optional): JWT; absent in session mode, where the cookie authenticates.
        """
        csrf_url = self.join_urls(self.base_url, "security/csrf_token/")
        logger.debug(f"Fetching CSRF token in: {csrf_url}")

        # 2. Obtain the CSRF token
        csrf_resp = RequestHandler.request_with_retry(
            url=csrf_url,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"} if access_token else {},
            verify=verify,
            session=session
        )

        self._csrf_token = csrf_resp.json()["result"]
        logger.debug("[OK] CSRF token successfully obtained.")
        if self._csrf_token:
            # Cookie required for Superset to accept CSRF
            # session.cookies.set("csrf_access_token", self._csrf_token, domain=self.get_domain())

            session.headers["X-CSRFToken"] = self._csrf_token
            # Flask-WTF compares the Referer with the host on HTTPS requests.
            session.headers["Referer"] = f"{self.host.rstrip('/')}/"
            logger.debug("CSRF token set successfully.")
        else:
            logger.warning("CSRF token not found in response.")

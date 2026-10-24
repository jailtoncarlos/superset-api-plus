import logging

import requests
from bs4 import BeautifulSoup

from supersetapiplus.transport.http import RequestHandler

logger = logging.getLogger(__name__)


class SessionAuthMixin:
    """
    Mixin for session-based authentication (via the 'session' cookie) using the Superset login form.

    This approach is required to access endpoints such as `/api/v1/me/` that require session-based authentication
    and do not work with JWT alone.
    """

    def enable_session_auth(self, session: requests.Session, username: str, password: str) -> None:
        """
        Authenticates with Superset via session (cookie). On success, the `session` cookie is stored in the session.

        Args:
            session (requests.Session): Requests session.
            username (str): Superset username.
            password (str): User password.
        """
        login_page_url = f"{self.host}/login/"
        logger.debug(f"[SessionAuth] Requesting login page to obtain CSRF: {login_page_url}")

        # Step 1: Get the CSRF token from the login page. The request must use the same session
        # as the POST: the form token is only valid together with the session cookie issued
        # here (Flask-WTF); without it Superset rejects the login and redirects to /login/.
        resp = RequestHandler.request_with_retry(
            url=login_page_url,
            method="GET",
            verify=self._verify,
            stream=False,
            headers={"Accept": "text/html"},
            session=session,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_token_input = soup.find("input", {"name": "csrf_token"})
        if not csrf_token_input or not csrf_token_input.get("value"):
            raise RuntimeError("CSRF token not found in the login form.")
        csrf_token = csrf_token_input["value"]
        logger.debug("[SessionAuth] CSRF token extracted.")

        # Step 2: Authenticate with credentials and CSRF token
        login_data = {
            "username": username,
            "password": password,
            "csrf_token": csrf_token,
        }
        login_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": login_page_url,
        }

        # POST with the given external session (not used directly by RequestHandler)
        response = session.post(
            login_page_url,
            data=login_data,
            headers=login_headers,
            verify=self._verify,
        )
        RequestHandler.raise_for_status(response)

        # Step 3: Check for success
        if "session" not in session.cookies:
            raise RuntimeError("Session authentication failed: 'session' cookie not found.")

        logger.info("[SessionAuth] Session authentication succeeded.")

import json
import logging
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests

from supersetapiplus.exceptions import SessionLoginError
from supersetapiplus.transport.http import RequestHandler

logger = logging.getLogger(__name__)

DEFAULT_LOGIN_PATH = "/login/"

# AUTH_TYPE values of Flask-AppBuilder 5 (flask_appbuilder/const.py). Only AUTH_DB and AUTH_LDAP log in through a
# form with a username and a password.
AUTH_TYPE_NAMES = {0: "AUTH_OID", 1: "AUTH_DB", 2: "AUTH_LDAP", 3: "AUTH_REMOTE_USER", 4: "AUTH_OAUTH"}
FORM_AUTH_TYPES = frozenset((1, 2))

NO_FORM_HINT = (
    "Session mode needs a database (or LDAP) login form. On an instance that logs people in through another "
    "AUTH_TYPE, either use the JWT mode (a local service user; note that endpoints the Public role can reach ignore "
    "the JWT when Public holds permissions) or expose a database login route for service accounts and pass its path "
    "to enable_session_mode(login_path=...) (see the README, 'Instances with OAuth login')."
)


class _LoginPageParser(HTMLParser):
    """What session mode reads from a Superset page: the ``csrf_token`` input of the login form and the
    ``data-bootstrap`` attributes (the standard library parser; attribute values come unescaped)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.csrf_token: str | None = None
        self.bootstraps: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        bootstrap = values.get("data-bootstrap")
        if bootstrap is not None:
            self.bootstraps.append(bootstrap)
        if tag == "input" and values.get("name") == "csrf_token" and self.csrf_token is None:
            self.csrf_token = values.get("value") or ""


def _parse(page: str) -> _LoginPageParser:
    parser = _LoginPageParser()
    parser.feed(page)
    parser.close()
    return parser


def page_auth_type(page: str) -> int | None:
    """The AUTH_TYPE Superset declares in the bootstrap data of a page (``common.conf.AUTH_TYPE``), if any."""
    for bootstrap in _parse(page).bootstraps:
        try:
            conf = json.loads(bootstrap).get("common", {}).get("conf", {})
        except (ValueError, AttributeError):
            continue
        auth_type = conf.get("AUTH_TYPE")
        if isinstance(auth_type, int):
            return auth_type
    return None


def _auth_type_name(auth_type: int | None) -> str:
    return AUTH_TYPE_NAMES.get(auth_type, str(auth_type)) if auth_type is not None else "unknown"


class SessionAuthMixin:
    """
    Mixin for session-based authentication (via the 'session' cookie) using the Superset login form.

    This approach is required to access endpoints such as `/api/v1/me/` that require session-based authentication
    and do not work with JWT alone.
    """
    # Provided by the client class the mixin is mixed into.
    host: str
    _verify: bool

    def enable_session_auth(self, session: requests.Session, username: str, password: str,
                            login_path: str = DEFAULT_LOGIN_PATH) -> None:
        """
        Authenticates with Superset via session (cookie). On success, the `session` cookie is stored in the session.

        Args:
            session (requests.Session): Requests session.
            username (str): Superset username.
            password (str): User password.
            login_path (str): path of the database login form; ``/login/`` unless the instance exposes another
                route for it (e.g. for service accounts on an instance with OAuth login).

        Raises:
            SessionLoginError: the page has no username and password form, or Superset refused the credentials.
        """
        login_page_url = urljoin(self.host.rstrip("/") + "/", login_path.lstrip("/"))
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
        # A page declaring an AUTH_TYPE without a form (e.g. AUTH_OAUTH) still carries a csrf_token, but its
        # /login/ does not take a POST (405): say so before posting the credentials.
        auth_type = page_auth_type(resp.text)
        if auth_type is not None and auth_type not in FORM_AUTH_TYPES:
            raise SessionLoginError(
                f"The login page {login_page_url} is for {_auth_type_name(auth_type)}, not a username and password "
                f"form. {NO_FORM_HINT}", auth_type=auth_type)
        csrf_token = _parse(resp.text).csrf_token
        if not csrf_token:
            raise SessionLoginError(f"CSRF token not found in the login form at {login_page_url}.", auth_type=auth_type)
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

        # POST with the given external session (not used directly by RequestHandler). The redirect tells the
        # outcome: Flask-AppBuilder sends a refused login back to a login page and a successful one elsewhere.
        response = session.post(
            login_page_url,
            data=login_data,
            headers=login_headers,
            verify=self._verify,
            allow_redirects=False,
        )
        if response.status_code == 405:
            raise SessionLoginError(
                f"The login page {login_page_url} does not take a username and password (405 Method Not Allowed; "
                f"AUTH_TYPE {_auth_type_name(auth_type)}). {NO_FORM_HINT}", auth_type=auth_type)
        RequestHandler.raise_for_status(response)

        # Step 3: Check for success
        location = urlsplit(response.headers.get("Location", "")).path
        if response.status_code != 302 or location.rstrip("/").endswith("/login"):
            raise SessionLoginError(
                f"Superset refused the session login of {username!r} at {login_page_url}: invalid username or "
                "password, or an inactive user.", auth_type=auth_type)
        if "session" not in session.cookies:
            raise SessionLoginError("Session authentication failed: 'session' cookie not found.", auth_type=auth_type)

        logger.info("[SessionAuth] Session authentication succeeded.")

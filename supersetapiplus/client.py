"""
SupersetClient - A fully authenticated client for Apache Superset REST API using JWT.

This class is responsible for authenticating with Superset using username/password via the /security/login endpoint,
and managing authenticated sessions using JWT access tokens. It provides access to
Superset core API modules such as charts, dashboards, datasets, and more.

Features:
- JWT-based login with support for automatic token refresh.
- Simplified access to Superset objects and query execution.
"""

import getpass
import json
import logging
from urllib.parse import urlparse

import requests
import requests.adapters
import requests.exceptions

from supersetapiplus.assets import Assets
from supersetapiplus.charts.charts import Charts
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.databases import Databases
from supersetapiplus.datasets import Datasets
from supersetapiplus.exceptions import QueryLimitReached, UnauthorizedError
from supersetapiplus.query_string import QueryStringFilter
from supersetapiplus.saved_queries import SavedQueries
from supersetapiplus.security.csrf import CSRFSupportMixin
from supersetapiplus.security.session_auth import SessionAuthMixin
from supersetapiplus.utils.request_handler import RequestHandler

logger = logging.getLogger(__name__)


class SupersetClient(CSRFSupportMixin, SessionAuthMixin):
    """Authenticated client for interacting with Superset REST API using JWT."""

    assets_cls = Assets
    dashboards_cls = Dashboards
    charts_cls = Charts
    datasets_cls = Datasets
    databases_cls = Databases
    saved_queries_cls = SavedQueries

    def __init__(self, host, username=None, password=None, provider="db",
                 verify=True, use_csrf=True):
        """
        Initializes the Superset client with API URL and credentials.

        Args:
            host (str): Base URL of Superset instance (e.g., http://localhost:8088).
            username (str, optional): Superset username.
            password (str, optional): Superset password.
            provider (str, optional): Authentication provider. Default is "db".
            verify (bool, optional): Verify SSL certificates. Default is True.
        """
        self.use_csrf = use_csrf

        self.host = host
        self._base_url = self.join_urls(host, "api/v1")
        self.username = username
        self._password = password
        self.provider = provider
        self._verify = verify

        self._session = None
        self._access_token = None
        self._refresh_token = None
        self._csrf_token = None
        self._session_mode = False

        # Object wrappers
        self.assets = self.assets_cls(self)
        self.dashboards = self.dashboards_cls(self)
        self.charts = self.charts_cls(self)
        self.datasets = self.datasets_cls(self)
        self.databases = self.databases_cls(self)
        self.saved_queries = self.saved_queries_cls(self)

    @property
    def base_url(self):
        return self._base_url

    @property
    def access_token(self):
        """Returns JWT token via login endpoint."""
        if self._access_token is None:
            self._init_session()
        return self._access_token

    @property
    def session(self) -> requests.Session:
        """Authenticated session (JWT, or cookie after enable_session_mode()), created on first use."""
        if self._session is None:
            self._init_session()
        return self._session

    @staticmethod
    def get_headers(headers: dict | None = None, json_body: bool = True) -> dict:
        """Request headers; JSON Content-Type only when the body is JSON (not for multipart)."""
        headers = dict(headers or {})
        if json_body:
            headers.setdefault("Content-Type", "application/json")
        return headers

    def _init_session(self):
        if self._session is not None:
            logger.debug('Reusing authenticated session.')
            return
        logger.debug('Initializing authenticated session...')
        session = requests.Session()
        session.verify = self._verify
        self.authenticate(session)
        if self.use_csrf:
            self.enable_csrf(session, self._access_token, verify=self._verify)
        self._session = session

    def enable_session_mode(self) -> requests.Session:
        """Initializes a cookie-based (non-JWT) authenticated session."""
        session = requests.Session()
        session.verify = self._verify
        self.enable_session_auth(session, self.username, self._password)
        # POST/PUT/DELETE with a cookie require the CSRF token ("The CSRF token is missing." in 6.1.0).
        if self.use_csrf:
            self.enable_csrf(session, verify=self._verify)
        self._session_cookie = session
        self._session = session
        self._session_mode = True
        self._access_token = self._refresh_token = None
        return self._session

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Authenticated request; in JWT mode, a 401 renews the token and retries the call once."""
        kwargs["headers"] = self.get_headers(kwargs.pop("headers", None), json_body="files" not in kwargs)
        kwargs.setdefault("verify", self._verify)
        try:
            return RequestHandler.request_with_retry(url=url, method=method, session=self.session, **kwargs)
        except UnauthorizedError:
            if self._session_mode or not self._refresh_token:
                raise
            self.refresh_access_token()
            return RequestHandler.request_with_retry(url=url, method=method, session=self.session, **kwargs)

    def get(self, url, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs) -> requests.Response:
        return self._request("POST", url, data=data, json=json, **kwargs)

    def put(self, url, data=None, **kwargs) -> requests.Response:
        return self._request("PUT", url, data=data, **kwargs)

    def delete(self, url, **kwargs) -> requests.Response:
        return self._request("DELETE", url, **kwargs)

    def authenticate(self, session: requests.Session):
        """
        Authenticates via JWT (POST /security/login) and stores the access and refresh tokens.
        """
        if self.username is None:
            self.username = getpass.getuser()
        if self._password is None:
            self._password = getpass.getpass()

        login_resp = RequestHandler.request_with_retry(
            url=self.login_endpoint,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "username": self.username,
                "password": self._password,
                "provider": self.provider,
                "refresh": True,
            },
            verify=self._verify,
            session=session
        )
        tokens = login_resp.json()
        self._access_token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token")
        session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        logger.debug("[OK] Token obtained successfully.")

    def refresh_access_token(self) -> None:
        """Renews the access JWT using the refresh token (POST /security/refresh)."""
        if not self._refresh_token:
            raise UnauthorizedError("No refresh token: authenticate again.")
        response = RequestHandler.request_with_retry(
            url=self.refresh_endpoint,
            method="POST",
            headers={"Authorization": f"Bearer {self._refresh_token}", "Accept": "application/json"},
            verify=self._verify,
        )
        self._access_token = response.json()["access_token"]
        self.session.headers["Authorization"] = f"Bearer {self._access_token}"
        logger.debug("[OK] Access token renewed.")

    def run(self, database_id: int, query: str, query_limit: int = None, schema: str | None = None):
        """
        Runs SQL through SQL Lab (POST /api/v1/sqllab/execute/), synchronously.

        Args:
            database_id (int): database id in Superset.
            query (str): SQL.
            query_limit (int, optional): row limit.
            schema (str, optional): default schema of the query.

        Returns:
            tuple: (columns, data), as returned by Superset.

        Raises:
            QueryLimitReached: the result was truncated by the display limit.
            NotImplementedError: Superset ran the query asynchronously (202).
        """
        payload = {"database_id": database_id, "sql": query, "runAsync": False}
        if query_limit:
            payload["queryLimit"] = query_limit
        if schema:
            payload["schema"] = schema

        response = self.post(self._sql_endpoint, json=payload)
        if response.status_code == 202:
            raise NotImplementedError("Superset ran the query asynchronously (202); "
                                      "use a database without asynchronous execution.")
        result = response.json()
        if result.get("displayLimitReached"):
            raise QueryLimitReached("Display limit reached")
        return result["columns"], result["data"]

    def find(self, url: str, filter: QueryStringFilter, columns: list[str] | None = None, page_size: int = 100,
             page: int = 0, order_column: str | None = None, order_direction: str | None = None):
        """
        Performs a paginated API search with optional filters.

        Args:
            url (str): API resource URL.
            filter (QueryStringFilter): Filter object.
            columns (List[str], optional): Columns to include.
            page_size (int): Number of records per page.
            page (int): Page index.
            order_column (str, optional): Column to sort by.
            order_direction (str, optional): "asc" or "desc".

        Returns:
            requests.Response: JSON response with `count` and `result`.
        """
        query = {"page_size": page_size, "page": page, "filters": filter.filters, "columns": columns or []}
        if order_column:
            query["order_column"] = order_column
            query["order_direction"] = order_direction or "asc"
        params = {"q": json.dumps(query)}
        return self.get(url, params=params)

    @property
    def login_endpoint(self) -> str:
        return self.join_urls(self.base_url, "security/login")

    @property
    def refresh_endpoint(self) -> str:
        return self.join_urls(self.base_url, "security/refresh")

    @property
    def _sql_endpoint(self) -> str:
        return self.join_urls(self.base_url, "sqllab/execute/")

    @staticmethod
    def join_urls(*args) -> str:
        """Joins parts of a URL ensuring proper formatting."""
        parts = [str(part).strip("/") for part in args]
        if str(args[-1]).endswith("/"):
            parts.append("")  # Preserve trailing slash
        return "/".join(parts)

    def get_domain(self):
        parsed = urlparse(self.base_url)
        domain = parsed.hostname
        return domain

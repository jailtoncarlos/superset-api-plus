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
import urllib.parse
from typing import List, Optional
from urllib.parse import urlparse

import requests
import requests.adapters
import requests.exceptions
from functools import cached_property

from supersetapiplus.assets import Assets
from supersetapiplus.charts.charts import Charts
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.databases import Databases
from supersetapiplus.datasets import Datasets
from supersetapiplus.exceptions import QueryLimitReached
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
        self._csrf_token = None

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

    @cached_property
    def session(self) -> requests.Session:
        """Returns a configured requests.Session with JWT headers."""
        if self._session is None:
            self._init_session()
        return self._session

    def get_headers(self, headers: Optional[dict] = None):
        if headers is None:
            headers = {}

        headers.update(
            {
                "Content-Type": "application/json",
            }
        )
        return headers

    def _init_session(self):
        if self._session is None:
            logger.debug('Initializing authenticated session...')
            session = requests.Session()

            # 1. Login and get token
            self.authenticate(session)

            session.verify = self._verify

            if not self._verify:
                session.mount(self.host, adapter=NoVerifyHTTPAdapter())

            if self.use_csrf:
                self.enable_csrf(session, self._access_token)

            self._session = session
        else:
            logger.debug('Reusing authenticated session.')
            print(f"Headers: {self._session.headers}")
            # print("Current CSRF token:", self._session.headers.get('X-CSRFToken'))
            print(f"Cookies: {self._session.cookies.get_dict()}")

    def enable_session_mode(self) -> requests.Session:
        """Inicializa uma sessão autenticada baseada em cookie (não JWT)."""
        session = requests.Session()
        self.enable_session_auth(session, self.username, self._password)
        self._session_cookie = session

        self._session = session

        return self._session

    def get(self, url, **kwargs) -> requests.Response:
        headers = self.get_headers(kwargs.pop("headers",  {}))
        return RequestHandler.request_with_retry(
            url=url,
            method="GET",
            headers=headers,
            session=self.session,
            **kwargs,
        )

    def post(self, url, data=None, json=None, **kwargs) -> requests.Response:
        headers = self.get_headers(kwargs.pop("headers",  {}))
        return RequestHandler.request_with_retry(
            url=url,
            method="POST",
            data=data,
            json=json,
            session=self.session,
            headers=headers,
            **kwargs,
        )

    def put(self, url, data=None, **kwargs) -> requests.Response:
        headers = self.get_headers(kwargs.pop("headers",  {}))
        return RequestHandler.request_with_retry(
            url=url,
            method="PUT",
            data=data,
            session=self.session,
            headers=headers,

            **kwargs,
        )

    def delete(self, url, **kwargs) -> requests.Response:
        headers = self.get_headers(kwargs.pop("headers",  {}))
        return RequestHandler.request_with_retry(
            url=url,
            method="DELETE",
            session=self.session,
            headers=headers,
            **kwargs,
        )

    def authenticate(self, session: requests.Session):
        """
        Authenticates the user and returns access/refresh tokens.
        """
        if self.username is None:
            self.username = getpass.getuser()
        if self._password is None:
            self._password = getpass.getpass()

        # 1. Login and obtain token
        login_resp = RequestHandler.request_with_retry(
            url=self.login_endpoint,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "username": self.username,
                "password": self._password,
                "provider": self.provider,
                "refresh": True,
            },
            verify=self._verify,
            session=session
        )
        self._access_token = login_resp.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        logger.debug(f"[OK] Token obtained successfully: {self._access_token[:40]}...")

    def run(self, database_id: int, query: str, query_limit: int = None):
        """
        Runs SQL query against Superset SQL Lab API.

        Args:
            database_id (int): Superset database ID.
            query (str): SQL query.
            query_limit (int, optional): Row limit.

        Returns:
            tuple: (columns, data) from query result.
        """
        payload = {"database_id": database_id, "sql": query}
        if query_limit:
            payload["queryLimit"] = query_limit

        response = RequestHandler.request_with_retry(
            url=self._sql_endpoint,
            method="POST",
            session=self.session,
            json=payload,
            verify=self._verify,
            headers=self.session.headers.copy(),  # Garante headers como Authorization e CSRF
        )

        result = response.json()
        if result.get("displayLimitReached"):
            raise QueryLimitReached("Display limit reached")
        return result["columns"], result["data"]

    def find(self, url: str, filter: QueryStringFilter, columns: List[str] = [], page_size: int = 100, page: int = 0):
        """
        Performs a paginated API search with optional filters.

        Args:
            url (str): API resource URL.
            filter (QueryStringFilter): Filter object.
            columns (List[str], optional): Columns to include.
            page_size (int): Number of records per page.
            page (int): Page index.

        Returns:
            dict: JSON response.
        """
        query = {"page_size": page_size, "page": page, "filters": filter.filters, "columns": columns}
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
        return self.join_urls(self.host, "superset/sql_json/")

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


class NoVerifyHTTPAdapter(requests.adapters.HTTPAdapter):
    """An HTTP adapter that disables TLS verification (for self-signed certs)."""
    def cert_verify(self, conn, url, verify, cert):
        logger.debug(f"conn: {conn}\nurl: {url}\nverify: {verify}\ncert: {cert}")
        super().cert_verify(conn=conn, url=url, verify=False, cert=cert)
"""A Superset REST Api Client."""
import getpass
import json
import logging
import urllib.parse
from typing import List

from supersetapiplus.query_string import QueryStringFilter

try:
    from functools import cached_property
except ImportError:  # pragma: no cover
    # Python<3.8
    from cached_property import cached_property

import requests.adapters
import requests.exceptions
import requests_oauthlib

from supersetapiplus.assets import Assets
from supersetapiplus.base.base import raise_for_status
from supersetapiplus.charts.charts import Charts
from supersetapiplus.dashboards.dashboards import Dashboards
from supersetapiplus.databases import Databases
from supersetapiplus.datasets import Datasets
from supersetapiplus.exceptions import QueryLimitReached
from supersetapiplus.saved_queries import SavedQueries

logger = logging.getLogger(__name__)


class SupersetClient:
    """A Superset Client."""

    assets_cls = Assets
    dashboards_cls = Dashboards
    charts_cls = Charts
    datasets_cls = Datasets
    databases_cls = Databases
    saved_queries_cls = SavedQueries

    def __init__(
        self,
        host,
        username=None,
        password=None,
        provider="db",
        verify=True,
    ):
        self.host = host
        self.base_url = self.join_urls(host, "api/v1")
        self._http_protocol = urllib.parse.urlparse(self.base_url).scheme

        self.username = username
        self._password = password
        self.provider = provider
        self._verify = verify

        # Related Objects
        self.assets = self.assets_cls(self)
        self.dashboards = self.dashboards_cls(self)
        self.charts = self.charts_cls(self)
        self.datasets = self.datasets_cls(self)
        self.databases = self.databases_cls(self)
        self.saved_queries = self.saved_queries_cls(self)

    @cached_property
    def _token(self):
        return self.authenticate()

    @cached_property
    def session(self):
        logger.debug(f'client.session ...')
        if self._http_protocol == 'https':
            return self._session_oath2()
        elif self._http_protocol == 'http':
            return self._session_http()

    def _session_http(self):
        logger.debug(f'client.__session_http ...')
        session = requests.Session()
        session.headers['Authorization'] = f"Bearer {self._token['access_token']}"

        # Update headers
        session.headers.update(
            {
                "X-CSRFToken": f"{self.csrf_token(session)}",
                "Referer": f"{self.base_url}",
            }
        )
        logger.debug(f'client.__session_http session.headers: {session.headers}')
        return session


    def _session_oath2(self):
        logger.debug(f'client._session_oath2 ...')
        session = requests_oauthlib.OAuth2Session(token=self._token)
        session.hooks["response"] = [self.token_refresher]

        session.verify = self._verify
        if not session.verify:
            session.mount(self.host, adapter=NoVerifyHTTPAdapter())

        # Update headers
        session.headers.update({
            "X-CSRFToken": f"{self.csrf_token(session)}",
            "Referer": f"{self.base_url}",
        })

        logger.debug(f'client._session_oath2 session.headers: {session.headers}')
        return session


    # Method shortcuts
    @property
    def get(self):
        return self.session.get

    @property
    def post(self):
        return self.session.post

    @property
    def put(self):
        return self.session.put

    @property
    def delete(self):
        return self.session.delete

    @staticmethod
    def join_urls(*args) -> str:
        """Join multiple url parts together.

        Returns:
            str: joined urls
        """
        parts = [str(part).strip("/") for part in args]
        if str(args[-1]).endswith("/"):
            parts.append("")  # Preserve trailing slash
        return "/".join(parts)

    def authenticate(self) -> dict:
        # Try authentication and define session
        if self.username is None:
            self.username = getpass.getuser()
        if self._password is None:
            self._password = getpass.getpass()

        # No need for session here because we are before authentication
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(
            self.login_endpoint,
            headers=headers,
            json={
                "username": self.username,
                "password": self._password,
                "provider": self.provider,
                "refresh": "true",
            },
        )
        raise_for_status(response)

        logger.debug(f'client.authenticate response: {response.json()}')
        return response.json()

    def token_refresher(self, r, *args, **kwargs):
        """A requests response hook for token refresh."""
        if r.status_code == 401:
            # Check if token has expired
            try:
                msg = r.json().get("msg")
            except requests.exceptions.JSONDecodeError:
                return r
            if msg != "Token has expired":
                return r
            refresh_token = self.session.token["refresh_token"]
            tmp_token = {"access_token": refresh_token}

            # Create a new session to avoid messing up the current session
            refresh_r = requests_oauthlib.OAuth2Session(token=tmp_token).post(self.refresh_endpoint)
            raise_for_status(refresh_r)

            new_token = refresh_r.json()
            if "refresh_token" not in new_token:
                new_token["refresh_token"] = refresh_token
            self.session.token = new_token

            # Set new authorization header
            bearer = f"Bearer {new_token['access_token']}"
            r.request.headers["Authorization"] = bearer

            return self.session.send(r.request, verify=False)
        return r

    def run(self, database_id, query, query_limit=None):
        """Sends SQL queries to Superset and returns the resulting dataset.

        :param database_id: Database ID of DB to query
        :type database_id: int
        :param query: Valid SQL Query
        :type query: str
        :param query_limit: limit size of resultset, defaults to -1
        :type query_limit: int, optional
        :raises Exception: Query exception
        :return: Resultset
        :rtype: tuple(dict)
        """
        payload = {
            "database_id": database_id,
            "sql": query,
        }
        if query_limit:
            payload["queryLimit"] = query_limit
        response = self.post(self._sql_endpoint, json=payload)
        raise_for_status(response)
        result = response.json()
        display_limit = result.get("displayLimit", None)
        display_limit_reached = result.get("displayLimitReached", False)
        if display_limit_reached:
            raise QueryLimitReached(
                f"You have exceeded the maximum number of rows that can be "
                f"returned ({display_limit}). Either set the `query_limit` "
                f"attribute to a lower number than this, or add LIMIT "
                f"keywords to your SQL statement to limit the number of rows "
                f"returned."
            )
        return result["columns"], result["data"]

    @property
    def password(self) -> str:
        return "*" * len(self._password)

    @property
    def login_endpoint(self) -> str:
        return self.join_urls(self.base_url, "security/login")

    @property
    def refresh_endpoint(self) -> str:
        return self.join_urls(self.base_url, "security/refresh")

    @property
    def _sql_endpoint(self) -> str:
        return self.join_urls(self.host, "superset/sql_json/")

    def csrf_token(self, session) -> str:
        # Get CSRF Token
        csrf_response = session.get(
            self.join_urls(self.base_url, "security/csrf_token/"),
            headers={"Referer": f"{self.base_url}"},
        )
        logger.debug(f'client.csrf_token Check CSRF ...')

        raise_for_status(csrf_response)  # Check CSRF Token went well

        logger.debug(f'client.csrf_token CSRF response: {csrf_response.json().get("result")}')
        return csrf_response.json().get("result")

    def find(self, url, filter:QueryStringFilter, columns:List[str]=[], page_size: int = 100, page: int = 0):
        """Find and get objects from api."""
        query = {
            "page_size": page_size,
            "page": page,
            "filters": filter.filters,
            "columns" :columns
        }
        logger.debug(f'client.find query string: {query}')

        params = {"q": json.dumps(query)}

        response = self.get(url, params=params)
        logger.debug(f'client.find response: {response.json()}')
        raise_for_status(response)
        return response.json()


class NoVerifyHTTPAdapter(requests.adapters.HTTPAdapter):
    """An HTTP adapter that ignores TLS validation errors"""

    def cert_verify(self, conn, url, verify, cert):
        logger.debug(f"conn: {conn}\nurl: {url}\nverify: {verify}\ncert: {cert}")
        super().cert_verify(conn=conn, url=url, verify=False, cert=cert)

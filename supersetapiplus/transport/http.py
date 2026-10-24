"""HTTP transport for the client: retries, timeouts, error mapping and masked logs."""
import logging
import os
from collections.abc import Iterable
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from supersetapiplus.core.masking import mask_body, mask_headers, mask_request_kwargs
from supersetapiplus.exceptions import (
    BadRequestError,
    ComplexBadRequestError,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)

logger = logging.getLogger(__name__)


def _number_from_env(name: str, default: float) -> float:
    """Read a network setting from the environment (e.g. SUPERSET_API_PLUS_TIMEOUT_READ=60), with a default."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return type(default)(value)
    except ValueError as err:
        raise ValueError(f"{name}={value!r} is not a valid number") from err


# Network defaults, tunable through environment variables without code changes; each call still
# accepts explicit timeout_connect/timeout_read/retries/backoff_factor.
TIMEOUT_CONNECT = _number_from_env("SUPERSET_API_PLUS_TIMEOUT_CONNECT", 10)
TIMEOUT_READ = _number_from_env("SUPERSET_API_PLUS_TIMEOUT_READ", 20)
DEFAULT_RETRIES = _number_from_env("SUPERSET_API_PLUS_RETRIES", 3)
DEFAULT_BACKOFF_FACTOR = _number_from_env("SUPERSET_API_PLUS_BACKOFF_FACTOR", 0.5)

# Transient failures worth retrying (429 honors the Retry-After header).
DEFAULT_STATUS_FORCELIST = (429, 500, 502, 503, 504)

# Only idempotent methods are retried: retrying a POST that failed on the server could create
# the resource twice. The exception is 429 (see RateLimitAwareRetry).
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
RATE_LIMITED = 429

HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})

STATUS_EXCEPTIONS = {
    401: UnauthorizedError,
    403: ForbiddenError,
    404: ResourceNotFoundError,
    422: UnprocessableEntityError,
}


class RateLimitAwareRetry(Retry):
    """Retries idempotent methods on transient failures, and any method on 429.

    A rate-limited request was rejected before being processed (RFC 6585), so repeating it cannot duplicate
    a resource. Superset in production mode limits every client (RATELIMIT_APPLICATION, 50 requests per
    second) and the login endpoint (AUTH_RATE_LIMIT).
    """

    def is_retry(self, method: str, status_code: int, has_retry_after: bool = False) -> bool:
        if status_code == RATE_LIMITED and status_code in (self.status_forcelist or ()) and self.total:
            return True
        return super().is_retry(method, status_code, has_retry_after)


class RequestHandler:
    """Runs the library's HTTP requests on top of a `requests.Session`."""

    @staticmethod
    def configure_retries(session: requests.Session, retries: float = DEFAULT_RETRIES,
                          backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
                          status_forcelist: Iterable[int] = DEFAULT_STATUS_FORCELIST) -> None:
        """Mount the retrying adapter on the session, once per configuration (reuses the connection pool)."""
        config = (int(retries), float(backoff_factor), tuple(status_forcelist))
        if getattr(session, "_supersetapiplus_retry", None) == config:
            return
        retry = RateLimitAwareRetry(
            total=config[0],
            backoff_factor=config[1],
            status_forcelist=config[2],
            allowed_methods=IDEMPOTENT_METHODS,
            respect_retry_after_header=True,
            # Once retries are exhausted, return the last response so raise_for_status can
            # convert the Superset error (previously a RetryError without the API message).
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session._supersetapiplus_retry = config  # type: ignore[attr-defined]  # marker of the mounted config

    @classmethod
    def request_with_retry(cls, url: str, method: str = "GET", session: requests.Session | None = None,
                           **kwargs: Any) -> requests.Response:
        """
        Perform an HTTP request, retrying transient failures and converting API errors.

        Args:
            url: request URL.
            method: "GET", "POST", "PUT" or "DELETE".
            session: authenticated session; without one, a new stateless session is used.
            **kwargs: headers, params, data, json, files, verify (None inherits session.verify), stream,
                timeout_connect, timeout_read, retries, backoff_factor, status_forcelist.

        Raises:
            UnauthorizedError, ForbiddenError, ResourceNotFoundError, UnprocessableEntityError,
            BadRequestError, ComplexBadRequestError: Superset error responses.
            requests.RequestException: connection failures and timeouts.
        """
        method = method.upper()
        if method not in HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method: {method}. Use {', '.join(sorted(HTTP_METHODS))}.")

        session = session or requests.Session()
        cls.configure_retries(
            session,
            retries=kwargs.get("retries", DEFAULT_RETRIES),
            backoff_factor=kwargs.get("backoff_factor", DEFAULT_BACKOFF_FACTOR),
            status_forcelist=kwargs.get("status_forcelist", DEFAULT_STATUS_FORCELIST),
        )

        logger.debug("Performing %s on %s ... kwargs: %s ...", method, url, mask_request_kwargs(kwargs))
        try:
            response = session.request(
                method,
                url,
                headers=kwargs.get("headers"),
                params=kwargs.get("params"),
                data=kwargs.get("data"),
                json=kwargs.get("json"),
                files=kwargs.get("files"),
                # None inherits `session.verify` (True by default in requests).
                verify=kwargs.get("verify"),
                stream=kwargs.get("stream", False),
                timeout=(kwargs.get("timeout_connect", TIMEOUT_CONNECT), kwargs.get("timeout_read", TIMEOUT_READ)),
            )
        except requests.exceptions.RequestException as err:
            logger.error("Network failure on %s %s: %s", method, url, err)
            raise

        cls.raise_for_status(response)
        logger.debug("Request %s to %s successful!", method, url)
        return response

    @classmethod
    def raise_for_status(cls, response: requests.Response) -> None:
        """
        Convert error responses into library exceptions, logging them masked.

        - 401/403/404/422: specific exception (BadRequestError subclasses), with `message` (for 422, the
          dict of errors per field) and `errors` (SIP-40 list), whatever the body format;
        - token rejected by flask-jwt-extended (body `{"msg": ...}`): UnauthorizedError with `msg` as the
          message, also for its 422 (malformed token, refresh token used as access token);
        - other statuses with `errors` (list of Superset errors): ComplexBadRequestError;
        - other statuses with `message`: BadRequestError; no recognizable body: requests.HTTPError.
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
            jwt_rejected = isinstance(body, dict) and "msg" in body and message is None and not errors
            if jwt_rejected:
                message = body["msg"]

            exception_class = UnauthorizedError if jwt_rejected else STATUS_EXCEPTIONS.get(response.status_code)
            if not exception_class and errors:
                exception_class = ComplexBadRequestError
            if exception_class or message:
                raise (exception_class or BadRequestError)(*e.args, request=request, response=response,
                                                           message=message, errors=errors) from None
            raise

    @staticmethod
    def _log_error(request: requests.PreparedRequest, response: requests.Response) -> None:
        # Headers and bodies are masked: they include Authorization, cookies, the CSRF token and,
        # on a rejected login, the password.
        request_headers = "\n".join(f"{k}: {v}" for k, v in mask_headers(request.headers).items())
        response_headers = "\n".join(f"{k}: {v}" for k, v in mask_headers(response.headers).items())
        try:
            response_body = mask_body(response.text)
        except Exception:
            response_body = "<could not decode the response body>"
        logger.error(
            "HTTP request error\nRequest URL: %s\nRequest Method: %s\nRequest Headers:\n%s\n"
            "Request Body:\n%s\nResponse Status Code: %s\nResponse Headers:\n%s\nResponse Body:\n%s",
            request.url, request.method, request_headers, mask_body(request.body) or "<empty>",
            response.status_code, response_headers, response_body,
        )

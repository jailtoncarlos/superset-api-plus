"""
Custom Exceptions module for superset-api-plus.

Defines specialized exception classes for error handling in the Superset API client,
including HTTP errors, validation errors, and domain-specific exceptions.
"""

import json
from typing import Any

from requests import HTTPError


class NotFound(Exception):
    """
    Raised when a requested resource is not found.

    Indicates that a lookup returned zero results when exactly one was expected.
    """
    pass


class MultipleFound(Exception):
    """
    Raised when a lookup returns multiple resources instead of exactly one.

    Indicates that more than one matching resource was found where only one was expected.
    """
    pass


class QueryLimitReached(Exception):
    """
    Raised when a query exceeds the maximum number of display rows configured in Superset.

    Used by the `run` method to halt processing if the Superset server reports that
    the display limit was reached.
    """
    pass


class BadRequestError(HTTPError):
    """
    Represents an HTTP error response from Superset (the base of the status-specific errors).

    `message` holds the `message` of the body (for 422, the errors per field) and `errors` the list of
    Superset errors (SIP-40 body `{"errors": [...]}`), when present; `str()` renders them as JSON.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.message: Any = kwargs.pop("message", None)
        self.errors: list[dict[str, Any]] | None = kwargs.pop("errors", None)
        super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        return json.dumps(self.message if self.message is not None else self.errors, indent=4)


class UnauthorizedError(BadRequestError):
    """HTTP 401: missing, invalid or expired credentials (the client tries to renew the JWT once)."""


class ForbiddenError(BadRequestError):
    """HTTP 403: authenticated user without permission for the resource."""


class ResourceNotFoundError(BadRequestError):
    """HTTP 404: resource does not exist in Superset (e.g. GET /chart/{id} with an invalid id)."""


class UnprocessableEntityError(BadRequestError):
    """HTTP 422: body rejected by schema validation; `message` holds the errors per field."""


class ComplexBadRequestError(BadRequestError):
    """
    Error response with a list of Superset errors (SIP-40 body) and a status without a specific class.

    401/403/404/422 bodies with `errors` raise the status class instead (with the same `errors`).
    """

    def __str__(self) -> str:
        return json.dumps(self.errors, indent=4)


class ItemPositionValidationError(Exception):
    """
    Raised for invalid dashboard item position specifications.

    Indicates that the provided position does not conform to expected rules or format.
    """
    pass


class AcceptChildError(Exception):
    """
    Raised when attempting to add a child item in a position that does not allow it.
    """

    def __init__(self, message: str = 'Item position does not allow including children'):
        super().__init__(message)


class LoadJsonError(Exception):
    """
    Raised when JSON loading or parsing fails.

    Indicates that provided content could not be converted to a valid JSON object.
    """
    pass


class ValidationError(Exception):
    """
    Generic validation error with an optional solution hint.

    Provides a `message` describing the validation failure and
    an optional `solution` suggesting how to correct the issue.
    """

    def __init__(self, message: str, solution: str | None = 'No solution provided.'):
        super().__init__(message, solution)
        self.message = message
        self.solution = solution


class NodePositionValidationError(ValidationError):
    """
    Validation error specific to node position constraints in trees or graphs.
    """

    def __init__(self, message: str, solution: str | None = None):
        super().__init__(message, solution)


class DashboardValidationError(ValidationError):
    """
    Validation error for dashboard configuration issues.
    """

    def __init__(self, message: str, solution: str | None = None):
        super().__init__(message, solution)


class ChartValidationError(ValidationError):
    """
    Validation error for chart configuration or usage issues.
    """

    def __init__(self, message: str, solution: str | None = None):
        super().__init__(message, solution)


class UnsupportedTypeError(NotImplementedError):
    """Object type (e.g. a chart viz_type) with no corresponding model in the library."""


class UnboundModelError(RuntimeError):
    """A model not bound to a Superset client was asked to reach the server (save, fetch, delete...)."""


class MissingCredentialsError(ValueError):
    """The client has no username or password to log in (the library never prompts for them)."""

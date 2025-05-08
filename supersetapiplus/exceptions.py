"""
Custom Exceptions module for superset-api-plus.

Defines specialized exception classes for error handling in the Superset API client,
including HTTP errors, validation errors, and domain-specific exceptions.
"""

import json
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
    Represents an HTTP 400 (Bad Request) error response.

    Accepts an optional `message` parameter containing details of the error,
    which will be rendered as formatted JSON when converted to string.
    """

    def __init__(self, *args, **kwargs):
        self.message = kwargs.pop("message", None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return json.dumps(self.message, indent=4)


class ComplexBadRequestError(HTTPError):
    """
    Represents an HTTP 400 error with multiple validation issues.

    Accepts an `errors` dictionary detailing each field or validation failure,
    which will be rendered as formatted JSON when converted to string.
    """

    def __init__(self, *args, **kwargs):
        self.errors = kwargs.pop("errors", None)
        super().__init__(*args, **kwargs)

    def __str__(self):
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

    def __init__(self, message: str, solution: str = 'No solution provided.'):
        super().__init__(message, solution)
        self.message = message
        self.solution = solution


class NodePositionValidationError(ValidationError):
    """
    Validation error specific to node position constraints in trees or graphs.
    """

    def __init__(self, message: str, solution: str = None):
        super().__init__(message, solution)


class DashboardValidationError(ValidationError):
    """
    Validation error for dashboard configuration issues.
    """

    def __init__(self, message: str, solution: str = None):
        super().__init__(message, solution)


class ChartValidationError(ValidationError):
    """
    Validation error for chart configuration or usage issues.
    """

    def __init__(self, message: str, solution: str = None):
        super().__init__(message, solution)

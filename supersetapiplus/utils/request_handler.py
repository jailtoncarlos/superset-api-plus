"""Deprecated module path: use :mod:`supersetapiplus.transport.http`."""
from supersetapiplus.deprecation import warn_renamed
from supersetapiplus.transport.http import *  # noqa: F401,F403

warn_renamed("supersetapiplus.utils.request_handler", "supersetapiplus.transport.http", stacklevel=2)

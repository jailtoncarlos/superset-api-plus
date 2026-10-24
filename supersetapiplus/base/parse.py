"""Deprecated module path: use :mod:`supersetapiplus.core.parse`."""
from supersetapiplus.core.parse import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.base.parse", "supersetapiplus.core.parse", stacklevel=2)

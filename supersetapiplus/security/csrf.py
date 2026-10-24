"""Deprecated module path: use :mod:`supersetapiplus.auth.csrf`."""
from supersetapiplus.auth.csrf import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.security.csrf", "supersetapiplus.auth.csrf", stacklevel=2)

"""Deprecated module path: use :mod:`supersetapiplus.core.datasource`."""
from supersetapiplus.core.datasource import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.base.datasource", "supersetapiplus.core.datasource", stacklevel=2)

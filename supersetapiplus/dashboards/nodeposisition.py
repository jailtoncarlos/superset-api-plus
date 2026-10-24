"""Deprecated module name (misspelled): use :mod:`supersetapiplus.dashboards.nodeposition`."""
from supersetapiplus.dashboards.nodeposition import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.nodeposisition", "supersetapiplus.dashboards.nodeposition", stacklevel=2)

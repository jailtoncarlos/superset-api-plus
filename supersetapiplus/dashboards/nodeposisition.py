"""Deprecated module name (misspelled): use :mod:`supersetapiplus.dashboards.layout.legacy.nodes`."""
from supersetapiplus.dashboards.layout.legacy.nodes import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.nodeposisition", "supersetapiplus.dashboards.layout.legacy.nodes", stacklevel=2)

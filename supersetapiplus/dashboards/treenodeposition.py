"""Deprecated module path: use :mod:`supersetapiplus.dashboards.layout.legacy.tree`."""
from supersetapiplus.dashboards.layout.legacy.tree import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.treenodeposition", "supersetapiplus.dashboards.layout.legacy.tree", stacklevel=2)

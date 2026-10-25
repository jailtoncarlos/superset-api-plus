"""Deprecated module path: use :mod:`supersetapiplus.dashboards.layout.legacy.items`."""
from supersetapiplus.dashboards.layout.legacy.items import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.itemposition", "supersetapiplus.dashboards.layout.legacy.items", stacklevel=2)

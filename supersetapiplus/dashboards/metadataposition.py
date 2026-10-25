"""Deprecated module path: use :mod:`supersetapiplus.dashboards.layout.legacy.metadata_position`."""
from supersetapiplus.dashboards.layout.legacy.metadata_position import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.metadataposition",
             "supersetapiplus.dashboards.layout.legacy.metadata_position", stacklevel=2)

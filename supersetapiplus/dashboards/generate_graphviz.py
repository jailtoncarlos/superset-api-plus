"""Deprecated module path: use :mod:`supersetapiplus.dashboards.layout.legacy.graphviz` (needs graphviz)."""
from supersetapiplus.dashboards.layout.legacy.graphviz import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.generate_graphviz", "supersetapiplus.dashboards.layout.legacy.graphviz",
             stacklevel=2)

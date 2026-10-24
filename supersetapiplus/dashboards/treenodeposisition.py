"""Deprecated module name (misspelled): use :mod:`supersetapiplus.dashboards.treenodeposition`."""
from supersetapiplus.dashboards.treenodeposition import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.dashboards.treenodeposisition", "supersetapiplus.dashboards.treenodeposition", stacklevel=2)

"""Deprecated module path: use :mod:`supersetapiplus.core.sentinels`."""
from supersetapiplus.core.sentinels import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.base.sentinels", "supersetapiplus.core.sentinels", stacklevel=2)

"""Deprecated module path: use :mod:`supersetapiplus.core.fields`."""
from supersetapiplus.core.fields import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.base.fields", "supersetapiplus.core.fields", stacklevel=2)

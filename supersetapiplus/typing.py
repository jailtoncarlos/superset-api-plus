"""Deprecated module path: use :mod:`supersetapiplus.core.typing`."""
from supersetapiplus.core.typing import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.typing", "supersetapiplus.core.typing", stacklevel=2)

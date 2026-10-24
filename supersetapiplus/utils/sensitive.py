"""Deprecated module path: use :mod:`supersetapiplus.core.masking`."""
from supersetapiplus.core.masking import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.utils.sensitive", "supersetapiplus.core.masking", stacklevel=2)

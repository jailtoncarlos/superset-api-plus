"""Deprecated module path: use :mod:`supersetapiplus.core.dicts`."""
from supersetapiplus.core.dicts import *  # noqa: F401,F403
from supersetapiplus.deprecation import warn_renamed

warn_renamed("supersetapiplus.utils.dict_utils", "supersetapiplus.core.dicts", stacklevel=2)


def dict_hash(my_dict):  # no longer used by the library; kept for old imports
    return hash(tuple(hash(item) for item in sorted(my_dict.items())))

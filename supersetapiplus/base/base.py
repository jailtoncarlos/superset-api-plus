"""Deprecated module path: the serialization moved to :mod:`supersetapiplus.core.model` and the HTTP
repositories to :mod:`supersetapiplus.resources.repository`."""
from supersetapiplus.core.api_model import ApiModel as SerializableModel  # noqa: F401
from supersetapiplus.core.model import *  # noqa: F401,F403
from supersetapiplus.core.model import FieldValue, ObjectDecoder  # noqa: F401
from supersetapiplus.deprecation import warn_renamed
from supersetapiplus.query_string import QueryStringFilter  # noqa: F401
from supersetapiplus.resources.repository import ApiModelFactories, UnsupportedObject  # noqa: F401

warn_renamed("supersetapiplus.base.base", "supersetapiplus.core.model / supersetapiplus.resources.repository",
             stacklevel=2)

"""Serialization of the models (no HTTP).

The models are pydantic: the base class is :class:`supersetapiplus.core.api_model.ApiModel`. This module keeps the
JSON encoder at its old path, and ``SerializableModel`` (the dataclass base the models had before) as a
deprecated alias of ApiModel.
"""
from typing import Any

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.encoding import ObjectDecoder as ObjectDecoder  # re-exported (old import path)
from supersetapiplus.core.encoding import enum_value as enum_value
from supersetapiplus.deprecation import module_aliases

FieldValue = str | int | bool | None | dict[str, Any] | list[Any]

__all__ = ["ApiModel", "FieldValue", "ObjectDecoder", "enum_value"]

# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"SerializableModel": "ApiModel"})

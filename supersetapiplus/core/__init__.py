"""Pure building blocks shared by every layer (no HTTP): models, fields, enums and masking of secrets."""
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.core.encoding import ObjectDecoder
from supersetapiplus.core.enums import StringEnum
from supersetapiplus.core.fields import default_bool, default_string, json_field, object_field
from supersetapiplus.core.masking import mask_body, mask_data, mask_headers
from supersetapiplus.core.references import DatasetRef, SavedChart, SavedDataset
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.types import ConfigurationMethod, DatasourceKind, DatasourceType, LimitingFactor
from supersetapiplus.core.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.deprecation import module_aliases

__all__ = [
    "DataSource", "StringEnum", "default_bool", "default_string", "json_field", "object_field", "mask_body",
    "mask_data", "mask_headers", "ObjectDecoder", "ApiModel", "MissingField", "ConfigurationMethod",
    "DatasourceKind", "DatasourceType", "LimitingFactor", "SerializableNotToJson", "SerializableOptional",
    "DatasetRef", "SavedChart", "SavedDataset",
]

# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"SerializableModel": "ApiModel"})

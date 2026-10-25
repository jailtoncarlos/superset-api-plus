"""Pydantic base of the models (no HTTP): ApiModel.

The models move from the dataclass ``SerializableModel`` to pydantic v2 (decided in the package reorganization);
``from_json``, ``to_dict``, ``to_json`` and ``validate`` stay as the facade. The rules are the ones of the
dataclass engine, so what the library writes does not change:

- reading (``from_json``) never loses data: a value pydantic would reject or coerce is kept as read, keys absent in
  the input stay absent (``MissingField``), unmodeled keys are kept and written back (``PRESERVE_EXTRA_FIELDS``);
- objects read from Superset skip the checks meant for objects built in code (``_read_from_superset``);
- ``SerializableOptional`` fields are left out while unset and ``SerializableNotToJson`` fields are never written;
- with ``convert_to_json`` the ``JSON_FIELDS`` become JSON text and every model is validated.
"""
import json
import logging
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from typing_extensions import Self

from supersetapiplus.core.dicts import dicts_equal_and_all_values_none
from supersetapiplus.core.encoding import ObjectDecoder
from supersetapiplus.core.masking import mask_data
from supersetapiplus.core.parse import ParseMixin
from supersetapiplus.core.persistence import PersistenceMixin
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import NOT_TO_JSON as _NOT_TO_JSON
from supersetapiplus.core.typing import OPTIONAL as _OPTIONAL
from supersetapiplus.exceptions import LoadJsonError

logger = logging.getLogger(__name__)

_READ = "read_from_superset"  # validation context: building from data stored by Superset
#: Serialization context key: JSON text fields and validation (``to_dict(convert_to_json=True)``).
CONVERT_TO_JSON = "convert_to_json"
_JSON = CONVERT_TO_JSON
_SCALARS = (str, int, float, bool)


class ApiModel(PersistenceMixin, ParseMixin, BaseModel):
    """A model of the Superset API (see the module docstring for the read and write rules)."""
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, protected_namespaces=(),
                              validate_default=False)

    # Fields stored by Superset as JSON text.
    JSON_FIELDS: ClassVar[list[str]] = []
    # Write back the unmodeled keys read (free-form structures); REST models with a strict schema disable it.
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = True
    # Fields accepted on create (POST) and update (PUT), per the OpenAPI specification (None: no restriction).
    POST_FIELDS: ClassVar[tuple[str, ...] | None] = None
    PUT_FIELDS: ClassVar[tuple[str, ...] | None] = None
    # Relations read as objects and sent as ids (owners, roles).
    ID_REFERENCE_FIELDS: ClassVar[tuple[str, ...]] = ()

    _factory: Any = None  # repository the object was read or created through (see PersistenceMixin)
    _request_response: Any = None  # HTTP response the object was read from, if any
    _read_from_superset: bool = False
    _read_keys: frozenset[str] = frozenset()  # fields present in the data read from Superset

    # --- reading -----------------------------------------------------------------------------------

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        """The object stored by Superset in `data`, read without loss (see the module docstring)."""
        try:
            return cls.model_validate_json(json.dumps(data, cls=ObjectDecoder), strict=True,
                                           context={_READ: True})
        except (ValidationError, ValueError, TypeError) as err:
            logger.exception("Error deserializing %s from %s", cls.__name__, mask_data(data))
            raise LoadJsonError(f"Error deserializing {cls.__name__}: {err}") from err

    @model_validator(mode="before")
    @classmethod
    def _load_json_fields(cls, data: Any, info: ValidationInfo) -> Any:
        """JSON_FIELDS given as JSON text are decoded ('null' becomes None); when reading, a required field absent
        from the stored data is MissingField (absent when written back) instead of a validation error."""
        if isinstance(data, dict) and any(isinstance(data.get(name), str) for name in cls.JSON_FIELDS):
            data = {key: json.loads(value) if key in cls.JSON_FIELDS and isinstance(value, str) else value
                    for key, value in data.items()}
        if isinstance(data, dict) and (info.context or {}).get(_READ):
            absent = [name for name, field in cls.model_fields.items() if field.is_required() and name not in data]
            data = {**data, **{name: MissingField() for name in absent}}
        return data

    @field_validator("*", mode="wrap")
    @classmethod
    def _keep_what_was_read(cls, value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
        """Data read from Superset is kept as stored: a value of another type than the field's stays as read,
        and a scalar is not converted (5 stays 5 in a float field, 'pie' stays a string in an enum field), also
        inside a list or a dict ([0, null] stays [0, null] in a list[float | None] field)."""
        if not (info.context or {}).get(_READ):
            return handler(value)
        try:
            result = handler(value)
        except ValidationError:
            return value
        return value if isinstance(value, (*_SCALARS, list, dict)) and result == value else result

    def model_post_init(self, context: Any) -> None:
        if (context or {}).get(_READ):
            self._read_from_superset = True
            self._read_keys = frozenset(self.model_fields_set)
            for name in type(self).model_fields:
                if name not in self.model_fields_set:  # absent key: stays absent when written back
                    self.__dict__[name] = MissingField()
        for name in self.JSON_FIELDS:
            value = getattr(self, name)
            # An empty structure, except for an optional field read from Superset: absent or null is kept, so
            # it is not written back as {} (a json_metadata without default_filters stays without it).
            if not (self._read_from_superset and _is_optional(type(self).model_fields[name])):
                value = value or "{}"
            if isinstance(value, str):
                self.__dict__[name] = json.loads(value)
        for name, info in type(self).model_fields.items():
            # None given in code to a field with a plain default (not an optional one) takes the default; a null
            # read from Superset stays null.
            if not self._read_from_superset and self.__dict__.get(name) is None \
                    and info.default not in (None, PydanticUndefined) and not _is_optional(info):
                self.__dict__[name] = info.default

    # --- writing -----------------------------------------------------------------------------------

    def to_dict(self, columns: list[str] | None = None, convert_to_json: bool = False) -> dict[str, Any]:
        """The fields to write (see the module docstring); `columns` adds attributes that are not fields."""
        if convert_to_json:  # outside the serializer, which would wrap the exceptions and drop the warnings
            self._check_tree()
        data: dict[str, Any] = self.model_dump(mode="python", warnings=False, context={_JSON: convert_to_json})
        for name in columns or []:
            value = getattr(self, name, MissingField())
            if name not in data and name not in type(self).model_fields and not isinstance(value, MissingField):
                data[name] = value.to_dict(None, convert_to_json) if isinstance(value, ApiModel) else value
        return data

    def to_json(self, columns: list[str] | None = None) -> dict[str, Any]:
        """The JSON payload: JSON_FIELDS as text, validated; `columns` restricts the top-level keys."""
        data = self.to_dict(columns, convert_to_json=True)
        if columns:
            data = {key: value for key, value in data.items() if key in columns}
        for name in self.ID_REFERENCE_FIELDS:
            if isinstance(data.get(name), list):
                data[name] = [item["id"] if isinstance(item, dict) else item for item in data[name]]
        logger.debug('return data %s', mask_data(data))
        return data

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> Any:
        if not isinstance(self, ApiModel):  # a field of a model type holding MissingField or a value kept as read
            return self
        data: dict[str, Any] = handler(self)
        fields = type(self).model_fields
        for name in list(data):
            if name in fields and self._left_out(name, fields[name], data[name]) \
                    or name not in fields and not self.PRESERVE_EXTRA_FIELDS:
                del data[name]
        if (info.context or {}).get(_JSON):
            for name in self.JSON_FIELDS:
                if name in data:  # None is sent as null, not as the text "null"
                    data[name] = None if data[name] is None else json.dumps(data[name], cls=ObjectDecoder)
        return data

    def _check_tree(self) -> None:
        """Checks before sending, nested models first."""
        for name in type(self).model_fields:
            _check_value(self.__dict__.get(name))
        self._check_before_sending()

    def _check_before_sending(self) -> None:
        self.validate()

    def _left_out(self, name: str, info: FieldInfo, serialized: Any) -> bool:
        value = self.__dict__.get(name)
        if isinstance(value, MissingField) or _NOT_TO_JSON in info.metadata:
            return True
        if not _is_optional(info):
            return False
        default = info.get_default(call_default_factory=True)
        if serialized is None:
            return default is None and not self._null_read_kept(name)
        return (isinstance(serialized, dict) and isinstance(default, ApiModel)
                and dicts_equal_and_all_values_none(serialized, default.to_dict()))

    def _null_read_kept(self, name: str) -> bool:
        """A null read in a structure nested in a resource (e.g. the params of a chart) is written back: leaving the
        key out would remove it. The fields of a REST resource and its JSON text fields are left out, which keeps
        what Superset stored."""
        return (self._read_from_superset and name in self._read_keys and name not in self.JSON_FIELDS
                and self.POST_FIELDS is None and self.PUT_FIELDS is None)

    # --- the rest of the facade ----------------------------------------------------------------------

    def validate(self) -> None:  # type: ignore[override]  # the facade method, not the deprecated classmethod
        """Checks of objects built in code; subclasses extend it."""

    @property
    def extra_fields(self) -> dict[str, Any]:
        """Unmodeled keys read or set on the object."""
        if self.__pydantic_extra__ is None:
            self.__pydantic_extra__ = {}
        return self.__pydantic_extra__

    @property
    def _extra_fields(self) -> dict[str, Any]:
        return self.extra_fields

    @classmethod
    def field_names(cls) -> list[str]:
        """Names of the model fields, in declaration order."""
        return list(cls.model_fields)

    def __eq__(self, other: object) -> bool:
        """Field by field, ignoring unmodeled keys and technical attributes."""
        if type(other) is not type(self):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in type(self).model_fields)

    __hash__ = None  # type: ignore[assignment]  # mutable


def _check_value(value: Any) -> None:
    if isinstance(value, ApiModel):
        value._check_tree()
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_value(item)
    elif isinstance(value, dict):
        for item in value.values():
            _check_value(item)


def _is_optional(info: FieldInfo) -> bool:
    return _OPTIONAL in info.metadata

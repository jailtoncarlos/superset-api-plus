"""Base classes."""
import dataclasses
import importlib
import logging
from abc import ABC, abstractmethod
from enum import Enum

from typing_extensions import Self

from supersetapiplus.base.sentinels import MissingField
from supersetapiplus.query_string import QueryStringFilter
from supersetapiplus.utils.dict_utils import dict_hash, dicts_equal_and_all_values_none
from supersetapiplus.utils.sensitive import mask_data

try:
    from functools import cached_property
except ImportError:  # pragma: no cover
    # Python<3.8
    from cached_property import cached_property

import json
import os.path
from pathlib import Path
from typing import Any, get_origin

import yaml

from supersetapiplus.base.parse import ParseMixin
from supersetapiplus.exceptions import LoadJsonError, MultipleFound, NotFound, UnsupportedTypeError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional

logger = logging.getLogger(__name__)

FieldValue = str | int | bool | None | dict[str, Any] | list[Any]


class ObjectDecoder(json.JSONEncoder):
    """
    Custom JSON encoder that serializes objects containing Enum instances.

    Overrides `json.JSONEncoder.default` so that `Enum` values are converted to
    their string representation (usually `value`), making it easy to serialize
    objects that use Enums as attributes.

    Example:
        >>> class Status(Enum):
        ...     OK = "ok"
        ...     FAIL = "fail"
        >>> json.dumps({'status': Status.OK}, cls=ObjectDecoder)
        '{"status": "ok"}'

    Methods:
        default(obj): returns `str(obj.value)` if `obj` is an Enum instance;
                      otherwise delegates to the default behavior.
    """

    def default(self, obj):
        # Convert Enum instances to their value as a string
        if isinstance(obj, Enum):
            return str(obj.value)
        return super().default(obj)


class SerializableModel(ParseMixin, ABC):
    """
    Abstract base class for objects that interact with the Superset API.

    Provides:
    - serialization and deserialization via JSON;
    - data validation;
    - conversion to dictionary (`to_dict`) and JSON (`to_json`);
    - support for extra fields not modeled directly;
    - comparison, hashing and data loading.

    Every subclass is assumed to be a `dataclass` whose fields mirror the structure expected by the API.

    Attributes:
        _factory: reference to the factory that manages instances of this object.
        JSON_FIELDS (List[str]): fields that must be serialized as JSON strings.
        _extra_fields (Dict): fields not mapped directly to class attributes.
    """
    _factory = None

    JSON_FIELDS = []

    _extra_fields: dict = {}

    # Re-emit in to_dict the unmodeled fields received in from_json. Needed for Superset's
    # free-form structures (params, query_context, json_metadata), where the library models
    # only some of the keys and dropping the rest would corrupt the object on save.
    # Models of REST endpoints with a strict schema (chart, dashboard, dataset...) disable it.
    PRESERVE_EXTRA_FIELDS = True

    # Fields accepted by the REST endpoint on create (POST) and update (PUT), per the
    # `{Resource}RestApi.post/.put` schemas of Superset's OpenAPI spec (checked in
    # tests/unit/test_openapi_conformance.py). None = no restriction. /_info cannot be used for this:
    # in 6.1.0 ChartRestApi declares add/edit_columns = ['slice_name'].
    POST_FIELDS: tuple[str, ...] | None = None
    PUT_FIELDS: tuple[str, ...] | None = None

    def validate(self):
        ...

    def __post_init__(self):
        """
        Run post-initialization steps for Object instances.

        Called automatically after a dataclass instance is created. It has two
        responsibilities:

        1. Deserialize the fields listed in `JSON_FIELDS` that were passed as strings.
           These fields are expected in JSON format and are converted to Python structures.

        2. Assign explicit default values to fields that:
            - have a default value defined;
            - were not filled in (value `None`) at instantiation;
            - are not `SerializableOptional` fields.

        This ensures required fields hold proper values, keeping the object's
        internal state consistent right after creation.
        """


        # Convert JSON_FIELDS passed as strings into Python dictionaries
        for f in self.JSON_FIELDS:
            value = getattr(self, f) or "{}"
            if isinstance(value, str):
                setattr(self, f, json.loads(value))

        # Iterate over all dataclass fields
        for field in self.fields():
            # If the field has a default, is currently None
            # and is not SerializableOptional,
            # set it to its default
            if not isinstance(field.default, dataclasses._MISSING_TYPE) \
                    and getattr(self, field.name) is None \
                    and get_origin(field.type) is not SerializableOptional:
                setattr(self, field.name, field.default)

    @property
    def extra_fields(self):
        return self._extra_fields

    def __eq__(self, other):
        """
        Compare this instance with another object for structural equality.

        Overrides `==` for `Object` instances. The comparison uses each object's internal
        attributes (`__dict__`), except `_extra_fields`, which is ignored because it is not
        part of the core serializable structure.

        Args:
            other (object): object to compare with.

        Returns:
            bool: `True` if the objects are equivalent in all relevant attributes; `False` otherwise.
                  Returns `NotImplemented` if the other object is not of the same type.

        Note:
            Subclasses decorated with `@dataclass` get an auto-generated `__eq__`,
            which also returns `NotImplemented` when the classes differ.
        """

        # Only objects of the same class are compared
        if not isinstance(other, type(self)):
            return NotImplemented

        # Copy the attributes so _extra_fields is not removed from the compared objects
        dict_self = {k: v for k, v in vars(self).items() if k != '_extra_fields'}
        dict_other = {k: v for k, v in vars(other).items() if k != '_extra_fields'}

        # True if the dictionaries are equal (equivalent attributes)
        return dict_self == dict_other

    def __ne__(self, other):
        # `not NotImplemented` is an error since Python 3.14 and, before that, silently
        # evaluated to False (objects of different classes treated as equal).
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        """
        Compute a hash for the instance from its internal attributes.

        Overrides the default `__hash__` so `Object` instances can be used as dictionary
        keys or stored in sets. `_extra_fields` is explicitly left out of the hash because
        it is not part of the object's essential serializable structure.

        Returns:
            int: hash computed from the object's main attributes.
        """

        # Get all instance attributes
        dict_self = vars(self)

        # Drop _extra_fields to keep the hash consistent
        dict_self.pop('_extra_fields', None)

        # Compute the hash with the project's helper function
        return dict_hash(dict_self)

    @classmethod
    def fields(cls) -> set:
        """
        Return the set of fields defined in the dataclass.

        Combines the fields declared in `__dataclass_fields__` with those returned by
        `dataclasses.fields`. Used to retrieve every attribute declaration of a class
        inheriting from `Object`.

        Returns:
            set: `dataclasses.Field` objects representing the class fields.
        """
        _fields = set()

        # Add fields declared directly on the class
        for f in cls.__dataclass_fields__.values():
            if isinstance(f, dataclasses.Field):
                _fields.add(f)

        # Also add the fields found by dataclasses.fields (may include inherited ones)
        _fields.update(dataclasses.fields(cls))

        return _fields

    @classmethod
    def get_field(cls, name) -> dataclasses.Field:
        """
        Return the dataclass field with the given name.

        Iterates over all dataclass fields and returns the one whose name
        matches the argument.

        Args:
            name (str): name of the field to look up.

        Returns:
            dataclasses.Field: the matching field, or None if not found.
        """
        for f in cls.fields():
            if f.name == name:
                return f

    @classmethod
    def field_names(cls) -> list:
        """
        Return the names of all fields defined in the dataclass.

        Fields whose default is an `Object` instance are skipped, since they
        represent complex sub-objects.

        Returns:
            list: names of the relevant fields.
        """
        fields = []
        for f in cls.fields():
            # Skip fields whose default is an Object instance
            if not isinstance(f.default, SerializableModel):
                fields.append(f.name)
        return fields

    @classmethod
    def required_fields(cls, data) -> dict:
        """
        Extract the dataclass's required fields from the given data.

        A field is required when it has no default (`MISSING`) and is not a
        complex `SerializeObject`-based field.

        Args:
            data (dict): raw data to check.

        Returns:
            dict: subset of the data containing only the required fields.
        """
        rdata = {}
        for f in cls.fields():
            if f.default is dataclasses.MISSING and not isinstance(f.default, SerializableModel):
                rdata[f.name] = data.get(f.name)
        return rdata

    @classmethod
    def __get_extra_fields(cls, data: dict) -> dict:
        """
        Extract the extra fields not defined as class attributes.

        Identifies the key-value pairs of `data` that do not match any field defined
        in the class. These "extra" fields are removed from the original dictionary
        and returned separately.

        Args:
            data (dict): input data, usually taken from a JSON response.

        Returns:
            dict: the extra fields not recognized as class attributes.
        """
        # Get the field names defined in the class
        # Get the keys present in the data dictionary
        # Compute the difference to find the unexpected keys
        # Remove and store the fields not defined in the class model

        if not data:
            return {}

        field_names = set(cls.field_names())  # Field names defined in the class

        data_keys = set(data.keys())  # Keys present in the received dictionary
        extra_fields_keys = data_keys - field_names  # Unknown keys
        extra_fields = {}
        for field_name in extra_fields_keys:
            extra_fields[field_name] = data.pop(field_name)  # Remove the extra fields from the original dictionary

        return extra_fields

    @classmethod
    def _subclass_object(cls, field: dataclasses.Field):
        """
        Retrieve the `Object` subclass associated with a dataclass field.

        Used to determine dynamically which object type must be instantiated
        while deserializing nested structures.

        The class is looked up at two levels:
        1. the field metadata (`cls`), usually passed through `object_field`;
        2. the `default_factory`, if it is an `Object` subclass.

        Args:
            field (dataclasses.Field): dataclass field whose type is inspected.

        Returns:
            Optional[Type[Object]]: the `Object` subclass, if found; otherwise `None`.
        """

        if field is None:
            return None

        # First try to get the class directly from the metadata, if available
        if hasattr(field, 'metadata'):
            if field.metadata.get("cls"):
                return field.metadata.get("cls")
        else:
            logger.warning(f'Field {field.name} has no "metadata" attribute. '
                           f'\nIf the field type is a subclass of "SerializableModel", '
                           f'check that the field was declared correctly with object_field.')

        # Then try to infer it from the default_factory
        default_factory = getattr(field, 'default_factory', None)

        if default_factory and default_factory is not dataclasses.MISSING:
            if isinstance(default_factory, type) and issubclass(default_factory, SerializableModel):
                return default_factory

        # If neither approach works, return None
        return None

    @classmethod
    def replace_none_with_custom(cls, obj):
        if isinstance(obj, dict):
            return {k: cls.replace_none_with_custom(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls.replace_none_with_custom(v) for v in obj]
        else:
            return obj

    @classmethod
    def instantiate_with_missing_check(cls, **data: Any):
        """
        Instantiate `cls` from keyword arguments, but:

          - Warn if any declared dataclass fields were not provided,
            and inject them into `data` with a `MissingField()` sentinel.
          - Warn if any extra keys were passed in.
          - Finally, call `cls(**filtered_data)` using exactly the declared fields.

        Returns:
            An instance of `cls`.
        """
        # 1) Determine all dataclass field names
        all_fields = {f.name for f in dataclasses.fields(cls)}
        provided = set(data.keys())

        # 2) Find missing and extra
        missing = all_fields - provided
        extra = provided - all_fields

        # 3) Warn and inject sentinel for missing fields
        if missing:
            for name in missing:
                data[name] = MissingField()

        # 4) Warn about any extra keys
        if extra:
            logger.warning(
                "%s: received unknown fields (will be ignored): %s",
                cls.__name__, sorted(extra)
            )
            # (we simply drop them below)

        # 5) Filter to exactly the dataclass fields
        filtered = {k: v for k, v in data.items() if k in all_fields}

        # 6) Instantiate
        return cls(**filtered)

    @classmethod
    def from_json(cls, data: dict) -> Self:
        """
        Build an instance of the class from a JSON dictionary.

        Deserializes an object of the class from a dictionary representing its
        attributes. Additional fields not defined in the class are captured in
        `_extra_fields`. It also deserializes nested JSON fields, lists of objects and
        objects with specific metadata, including structures that use `dict_right`.

        During the process, `None` values are replaced by `CUSTOM_NONE` instances,
        preserving the semantics of a missing value without clashing with a literal absence.

        Args:
            data (dict): data to map onto an instance of the class.

        Returns:
            Self: a new instance of the class, populated with the given data.

        Raises:
            LoadJsonError: if mapping any field fails, including structure, type or
                           parsing errors in composite fields.
        """
        extra_fields = cls.__get_extra_fields(data)  # Split off fields not defined in the class
        field_name = None
        data_value = None

        try:
            logger.debug('Instantiating %s with data: %s', cls.__name__, mask_data(data))
            obj = cls.instantiate_with_missing_check(**data)

            for field_name in cls.JSON_FIELDS:
                logger.debug(f'field_name: {field_name} found in JSON_FIELDS')
                data_value = data.get(field_name)
                if isinstance(data_value, str):
                    field = cls.get_field(field_name)
                    serializable_object_class = cls._subclass_object(field)
                    value = json.loads(data[field_name])
                    # 'null' stored as text (e.g. the query_context of an imported chart) becomes None,
                    # without going through the subclass's from_json.
                    if serializable_object_class and value is not None:
                        value = serializable_object_class.from_json(value)
                    setattr(obj, field_name, value)

            for field_name, data_value in data.items():
                logger.debug('field_name: %s; data_value: %s', field_name, mask_data({field_name: data_value}))
                if field_name in cls.JSON_FIELDS:
                    continue

                if isinstance(data_value, dict):
                    value = data_value
                    field = cls.get_field(field_name)
                    serializable_object_class = cls._subclass_object(field)
                    if serializable_object_class and field.metadata.get('dict_right'):
                        value = {k: serializable_object_class.from_json(v) for k, v in data_value.items()}
                    elif serializable_object_class:
                        value = serializable_object_class.from_json(data_value)

                    setattr(obj, field_name, value)

                elif isinstance(data_value, list):
                    field = cls.get_field(field_name)
                    serializable_object_class = cls._subclass_object(field)
                    value = []
                    field_value = None
                    for field_value in data_value:
                        if serializable_object_class and isinstance(field_value, dict):
                            try:
                                value.append(serializable_object_class.from_json(field_value))
                            except Exception as err:
                                msg = f"""unhandled exception: {err}
                                    cls={cls}
                                    field_name={field_name}
                                    data_value={data_value}
                                    data={data}
                                    extra_fields={extra_fields}
                                """
                                logger.warning(msg)
                                raise
                        else:
                            value.append(field_value)
                    setattr(obj, field_name, value)

                else:
                    setattr(obj, field_name, data_value)

            obj._extra_fields = extra_fields

        except Exception as err:
            msg = f"""Error deserializing list item
                cls={cls}
                field_name={field_name}
                data_value={data_value}
                data={data}
                extra_fields={extra_fields}
                the cause of the error is shown above: {err}
            """
            logger.exception(msg)
            raise LoadJsonError(msg) from err

        return obj

    @classmethod
    def _is_exclude(cls, value: FieldValue, field_name: str, convert_to_json: bool = False):
        exclude = False

        if isinstance(value, list):
            for v in value:
                return cls._is_exclude(v, field_name, convert_to_json)

        field = cls.get_field(field_name)
        try:
            default_value = None
            if field.default is not dataclasses.MISSING:
                default_value = field.default
            elif field.default_factory is not dataclasses.MISSING:
                default_value = field.default_factory()

            if isinstance(value, MissingField):
                exclude = True
            # Always exclude fields marked as SerializableNotToJson
            elif get_origin(field.type) is SerializableNotToJson:
                exclude = True
            # Exclude SerializableOptional fields when the value is missing or equals the default
            elif get_origin(field.type) is SerializableOptional:
                if not value and default_value is dataclasses.MISSING:
                    exclude = True
                elif value is None and default_value is None:
                    exclude = True
                elif isinstance(value, dict):
                    if isinstance(default_value, SerializableModel):
                        all_none = dicts_equal_and_all_values_none(value, default_value.to_dict())
                        if all_none:
                            exclude = True
                else:
                    exclude = False

        except Exception as err:
            logger.warning(f'Ignoring error while checking whether field "{field_name}" should be excluded, Error: {err}')
            pass

        if exclude:
            logger.debug(f"exclude field_name: {field_name}, value: {value}")
        return exclude

    def to_dict(self, columns: list = None, convert_to_json: bool = False) -> dict:
        """
        Serialize the object into a Python dictionary, converting every relevant field.

        Serialization covers the explicitly listed columns or, if omitted, all of the object's columns.
        `Object` fields, `Enum`s, lists, tuples and nested dictionaries get special handling
        to stay compatible with JSON formats.

        Tuples are converted recursively, with support for `Object` and `Enum`.
        Dictionaries with `dict_left` or `dict_right` metadata are transformed following
        the given directions.

        Args:
            columns (list, optional): names of the fields to include.
                If empty, all fields defined in the class are serialized.

        Returns:
            dict: dictionary representing the object's current state, with the fields converted.
        """
        def prepare_value_tuple(field_name: str, field_value: tuple, columns: list, convert_to_json: bool) -> tuple:
            """Convert a (value, key) pair, e.g. an orderby item, converting each element.

            Returns the pair itself: it used to return a list containing the pair, and orderby
            came out with an extra list level ([[["count", true]]] instead of [["count", true]]).
            """
            # A pair is always expected; a tuple of any other length is usually a stray comma
            # in the field declaration of the @dataclass.
            if len(field_value) != 2:
                raise ValueError(
                    f"Invalid default for dataclass field '{field_name}': "
                    f"got tuple of length {len(field_value)}. "
                    "This usually happens when there is an extra comma after a "
                    "field declaration in a @dataclass class. Remove the "
                    "extra comma and try again."
                )
            return tuple(prepare_tuple_item(item, convert_to_json) for item in field_value)

        def prepare_tuple_item(item, convert_to_json: bool):
            if isinstance(item, SerializableModel):
                return item.to_dict(columns_names, convert_to_json)
            if isinstance(item, Enum):
                return str(item)
            return item

        # Merge the explicit columns with those defined in the class
        columns_names = set(columns or [])
        columns_names.update(self.field_names())

        data = {}
        for field_name in columns_names:
            if not hasattr(self, field_name):  # Skip columns not mapped yet
                continue

            value = getattr(self, field_name)

            if isinstance(value, MissingField):
                # logger.warning(f"field_name {field_name} typeof MissingField.")
                continue

            # Convert Enums to string
            if isinstance(value, Enum):
                value = str(value)

            # Convert objects recursively
            elif value and isinstance(value, SerializableModel):
                value = value.to_dict(columns_names, convert_to_json)

            # Convert lists of objects, tuples or enums
            elif value and isinstance(value, list):
                values_data = []
                for field_value in value:
                    if isinstance(field_value, SerializableModel):
                        values_data.append(field_value.to_dict(columns_names, convert_to_json))
                    elif isinstance(field_value, tuple):
                        values_data.append(prepare_value_tuple(field_name, field_value, columns, convert_to_json))
                    elif isinstance(field_value, Enum):
                        values_data.append(str(field_value))
                    else:
                        values_data.append(field_value)
                    value = values_data

            # Convert dictionaries of objects based on metadata
            elif value and isinstance(value, dict):
                field = self.get_field(field_name)
                serializable_object_class = self._subclass_object(field)
                if serializable_object_class:
                    _value = {}
                    if field.metadata.get('dict_left'):
                        for obj, value_ in value.items():
                            key = obj.to_dict(columns_names, convert_to_json)
                            _value[key] = value_
                    elif field.metadata.get('dict_right'):
                        for k, obj in value.items():
                            _value[k] = obj.to_dict(columns_names, convert_to_json)
                    value = _value

            # Convert plain tuples
            elif value and isinstance(value, tuple):
                value = prepare_value_tuple(field_name, value, columns, convert_to_json)

            if not self.__class__._is_exclude(value, field_name, convert_to_json):
                if convert_to_json and field_name in self.JSON_FIELDS:
                    # None is sent as null, not as the text "null" (which Superset would store literally).
                    data[field_name] = None if value is None else json.dumps(value, cls=ObjectDecoder)
                else:
                    data[field_name] = value

        if self.PRESERVE_EXTRA_FIELDS:
            for extra_name, extra_value in (self._extra_fields or {}).items():
                data.setdefault(extra_name, extra_value)

        copydata = data
        # Remove the technical "_extra_fields" field if still present
        if data.get('extra_fields'):
            copydata = data.copy()
            logger.debug(f'removing technical field _extra_fields: {copydata}')
            copydata.pop('extra_fields')

        if convert_to_json:
            self.validate()

        return copydata

    def to_json(self, columns: list = None) -> dict:
        """
        Serialize the object into a JSON-ready dictionary, with support for nested fields.

        Converts the object into a dictionary suitable for JSON export, applying specific
        serialization rules to the fields in `JSON_FIELDS` (stored as JSON strings),
        dropping unfilled optional fields and excluding fields marked as non-serializable
        (`SerializableNotToJson`).

        Args:
            columns (list, optional): names of the fields to include in the export.
                If omitted, all fields defined in the class are considered.

        Returns:
            dict: dictionary ready for JSON serialization.
        """
        if columns is None:
            columns = []

        # First convert the whole object into a plain dictionary (recursively)
        data = self.to_dict(columns, convert_to_json=True)

        # `columns` restricts the top-level fields (to_dict merges the list with the model fields
        # to serialize nested objects, so without this filter the argument had no effect).
        if columns:
            data = {k: v for k, v in data.items() if k in columns}

        # Log the final structure before returning it
        logger.debug('return data %s', mask_data(data))

        return data

    @property
    def base_url(self) -> str:
        """
        Return the base URL of this object instance.

        Uses the factory's client to build the URL by joining the base endpoint
        with the current object's identifier (`id`).

        Returns:
            str: full URL for operations on the object.
        """
        return self._factory.client.join_urls(self._factory.base_url, self.id)

    def export(self, path: Path | str) -> None:
        """
        Export the current object's data to a file at the given path.

        Args:
            path (Union[Path, str]): destination path for the exported content.
        """
        self._factory.export(ids=[self.id], path=path)

    def fetch(self) -> None:
        """
        Reload the instance data from the remote API.

        Performs a GET request on the object URL and updates the instance attributes
        with the returned values, deserializing the JSON fields listed in `JSON_FIELDS`.
        """
        field_names = self.field_names()
        client = self._factory.client
        response = client.get(self.base_url)
        o = response.json().get("result")

        for k, v in o.items():
            if k in field_names:
                if k in self.JSON_FIELDS:
                    # Convert the JSON string into a Python dictionary
                    setattr(self, k, json.loads(v or "{}"))
                else:
                    setattr(self, k, v)

    def save(self) -> None:
        """
        Update or persist the object's data in the remote API.

        Converts the instance's current data to JSON and sends it to the API in a PUT
        request. Logs the payload and the response.
        """
        # Send the model fields. /_info cannot be used as a filter: in Superset 6.1.0
        # ChartRestApi declares edit_columns = ['slice_name'], but validates the body with
        # ChartPutSchema, which requires/accepts datasource_id, params, query_context etc.
        payload = self.to_json(columns=list(self.PUT_FIELDS or []))
        payload.pop("id", None)

        logger.debug('payload: %s', mask_data(payload))

        response = self._factory.client.put(self.base_url, json=payload)
        logger.debug('response: %s', mask_data(response.json()))

    def delete(self) -> bool:
        """
        Delete the object from the remote API.

        Returns:
            bool: `True` if the deletion succeeded, `False` otherwise.
        """
        return self._factory.delete(id=self.id)

    def get_request_response(self):
        """
        Return the raw response of the last request associated with the object.

        Returns the JSON content with the fields listed in `JSON_FIELDS`
        deserialized from JSON strings.

        Returns:
            dict: JSON structure with the response data, including converted fields.
        """
        jdict = self._request_response.json()
        # for field_name in self.JSON_FIELDS:
        #     jdict['result'][field_name] = json.loads(jdict['result'][field_name])
        # return jdict
        return jdict


class UnsupportedObject:
    """Listing item whose type has no model in the library (e.g. an unsupported viz_type).

    Returned by `find()` so that a single unknown item does not break the whole listing.
    Exposes the received fields as attributes (`id`, `slice_name`, `viz_type`...) and the original
    dict in `data`. It is read-only: it has no `save()`; `get(id)` on the same item raises
    `UnsupportedTypeError`.
    """

    def __init__(self, data: dict, factory=None):
        self.data = dict(data)
        self.__dict__.update(self.data)
        self._factory = factory

    def __repr__(self):
        return f"UnsupportedObject(id={self.data.get('id')!r}, viz_type={self.data.get('viz_type')!r})"


class ApiModelFactories(ABC):
    """
    Abstract base class for factories of objects that interact with the Superset API.

    Encapsulates the communication with Superset's RESTful endpoints, allowing the
    handling of entities such as charts, datasets and databases. Subclasses must
    specify the default object class and the corresponding endpoint.

    Provides methods to:
    - find objects by ID or filters
    - create, update and delete objects
    - import and export objects via JSON or ZIP files
    - get endpoint meta-information (_info)
    """

    endpoint = ""
    _INFO_QUERY = {"keys": ["add_columns", "edit_columns"]}

    def __init__(self, client):
        """
        Initialize the factory with the client that performs the HTTP requests.

        Args:
            client: client instance wrapping the request methods (GET, POST, DELETE, etc.)
        """
        self.client = client

    @abstractmethod
    def _default_object_class(self) -> type[SerializableModel]:
        """
        Must be implemented by subclasses to return the default class of the handled objects.
        """
        ...

    def get_base_object(self, data: dict | None = None):
        """
        Returns the class to be instantiated based on the 'viz_type' field in the provided data.

        Args:
            data (Optional[Dict]): A dictionary of entity data returned by the API.
                If None is passed, an empty dict is used.

        Returns:
            Type[SerializableModel]: The class corresponding to the specified viz_type,
                or the default object class if no viz_type is present.
        """
        if data is None:
            data = {}

        type_ = data.get('viz_type')
        if type_:
            m = self._default_object_class().__module__.split('.')
            # Remove the last segment, which is the parent class name
            m.pop(-1)

            m.append(type_)

            module_name = '.'.join(m)

            # Import the type's module on demand; previously it only worked if the module
            # had already been imported some other way (sys.modules).
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as e:
                if e.name != module_name:
                    raise
                raise UnsupportedTypeError(
                    f"viz_type '{type_}' is not supported by superset-api-plus "
                    f"(module '{module_name}' not found)."
                ) from e

            return self._default_object_class().get_class(type_, module_name)

        return self._default_object_class()

    @cached_property
    def _infos(self):
        """
        Get endpoint meta-information, such as the columns available for adding and editing.

        Returns:
            dict: data returned by the /_info endpoint.
        """
        response = self.client.get(self.info_url, params={"q": json.dumps(self._INFO_QUERY)})
        return response.json()

    @property
    def add_columns(self):
        """Columns available for adding."""
        return [e.get("name") for e in self._infos.get("add_columns", [])]

    @property
    def edit_columns(self):
        """Columns available for editing."""
        return [e.get("name") for e in self._infos.get("edit_columns", [])]

    @property
    def base_url(self):
        """Return the base URL of the current endpoint."""
        url = self.client.join_urls(self.client.base_url, self.endpoint)
        logger.info(f'url: {url}')
        return url

    @property
    def info_url(self):
        """URL to get information about the endpoint schema."""
        return self.client.join_urls(self.base_url, "_info")

    @property
    def import_url(self):
        """URL for importing objects."""
        return self.client.join_urls(self.base_url, "import/")

    @property
    def export_url(self):
        """URL for exporting objects."""
        return self.client.join_urls(self.base_url, "export/")

    def get(self, id: str):
        """
        Fetch and instantiate an object through an HTTP request for the given ID.

        Performs a GET request to the URL formed by joining `base_url` with the given `id`.
        The JSON response is converted into a Python dictionary, with `None` fields replaced
        by a custom value (`CUSTOM_NONE`). A base class is then determined dynamically and
        the corresponding object is instantiated from the data.

        The resulting instance keeps references to the original response (`_request_response`)
        and to the originating factory (`_factory`), for tracing and later reuse.

        Args:
            id (str): unique identifier of the resource to fetch.

        Returns:
            SerializableModel: instance of the appropriate base class, representing the returned resource.

        Raises:
            requests.HTTPError: if the HTTP response indicates an error (status != 2xx).
            LoadJsonError: if deserializing the JSON content fails.
        """

        # Build the request URL by joining the base with the resource identifier
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')

        # Perform the HTTP GET request on the endpoint
        response = self.client.get(url)

        # Convert the JSON response body into a Python dictionary
        result = response.json()
        logger.debug('response: %s', mask_data(result))

        # Get the main resource content from the 'result' key
        data_result = result['result']

        # Make sure the 'id' field is present in the main dictionary
        data_result["id"] = result.get('id', data_result.get('id', id))

        # Dynamically determine the appropriate base class from the data
        BaseClass = self.get_base_object(data_result)

        # Instantiate the object through the deserialization method
        obj = BaseClass.from_json(data_result)

        # Store additional metadata on the instance
        obj._request_response = response  # Reference to the original response
        obj._factory = self  # Reference to the factory used

        return obj

    def find(self, filter: QueryStringFilter, columns: list[str] | None = None, page_size: int = 100, page: int = 0,
             order_column: str | None = None, order_direction: str | None = None):
        """
        Find objects using filters and pagination.

        Args:
            filter (QueryStringFilter): filter applied to the query string.
            columns (List[str]): columns to return.
            page_size (int): size of the results page.
            page (int): page number.
            order_column (str, optional): sort column; order_direction "asc" or "desc".

        Returns:
            List[SerializableModel]: objects found (UnsupportedObject for types without a model).
        """
        response = self.client.find(self.base_url, filter, columns, page_size, page, order_column, order_direction)
        data_result = response.json()

        objects = []
        for data in data_result.get("result"):
            try:
                base_class = self.get_base_object(data)
            except UnsupportedTypeError:
                objects.append(UnsupportedObject(data, factory=self))
                continue
            o = base_class.from_json(data)
            o._request_response = response
            o._factory = self
            objects.append(o)
        return objects

    def find_all(self, filter: QueryStringFilter | None = None, columns: list[str] | None = None,
                 page_size: int = 100, order_column: str | None = None, order_direction: str | None = None):
        """Find across all pages; same parameters as `find`."""
        filter = filter or QueryStringFilter()
        objects, page = [], 0
        while True:
            page_objects = self.find(filter, columns, page_size, page, order_column, order_direction)
            objects.extend(page_objects)
            if len(page_objects) < page_size:
                return objects
            page += 1

    def count(self, filter: QueryStringFilter | None = None) -> int:
        """
        Return the number of objects in the endpoint, optionally restricted by a filter.

        Returns:
            int: object count.
        """
        if filter is None:
            return self.client.get(self.base_url).json()["count"]
        return self.client.find(self.base_url, filter, ["id"], page_size=1).json()["count"]

    def find_one(
            self,
            filter: QueryStringFilter,
            columns: list[str] | None = None,
            full: bool = False,
    ):
        """
        Find a single object using a filter.

        Args:
            filter (QueryStringFilter): search filters.
            columns (List[str], optional): columns to return.
            full (bool, optional): if True, reload the object by ID with complete data.

        Raises:
            NotFound: no object found.
            MultipleFound: more than one object found.

        Returns:
            SerializableModel: the object found.
        """
        objects = self.find(filter, columns)
        if len(objects) == 0:
            raise NotFound(f"No {self.get_base_object().__name__} found")
        if len(objects) > 1:
            raise MultipleFound(f"Multiple {self.get_base_object().__name__} found")

        obj = objects[0]
        if full and hasattr(obj, "id"):
            obj = self.get(obj.id)  # Reload with complete data via ID
        return obj

    def add(self, obj) -> int:
        """
        Add a new object to the remote endpoint.

        Args:
            obj (SerializableModel): object to add.

        Returns:
            int: ID of the created object.
        """

        # Model fields, not the add_columns from /_info (see save()): in 6.1.0 the chart _info
        # lists only slice_name and the POST requires datasource_id/datasource_type (ChartPostSchema).
        payload = obj.to_json(columns=list(obj.POST_FIELDS or []))
        payload.pop("id", None)

        logger.debug('payload: %s', mask_data(payload))
        response = self.client.post(self.base_url, json=payload)
        result = response.json()
        logger.debug('response: %s', mask_data(result))
        obj.id = result.get("id")
        obj._factory = self
        return obj.id

    def export(self, ids: list[int], path: Path | str) -> None:
        """
        Export objects to a file in a compatible format (ZIP, JSON or YAML).

        Args:
            ids (List[int]): IDs of the objects to export.
            path (Path | str): destination file path.
        """
        ids_array = ",".join([str(i) for i in ids])
        response = self.client.get(self.export_url, params={"q": f"[{ids_array}]"})
        content_type = response.headers["content-type"].strip()

        if content_type.startswith("application/text"):
            data = yaml.load(response.text, Loader=yaml.FullLoader)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)
        elif content_type.startswith("application/json"):
            data = response.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        elif content_type.startswith("application/zip"):
            data = response.content
            with open(path, "wb") as f:
                f.write(data)
        else:
            raise ValueError(f"Unknown content type {content_type}")

    def delete(self, id: int) -> bool:
        """
        Remove an object from the remote endpoint.

        Args:
            id (int): object identifier.

        Returns:
            bool: True if the deletion succeeded.
        """
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')
        response = self.client.delete(url)
        logger.debug('response: %s', mask_data(response.json()))
        return response.json().get("message") == "OK"

    def import_file(self, file_path, overwrite=False, passwords=None) -> dict:
        """
        Import a file (JSON or ZIP) into Superset.

        Args:
            file_path (str | Path): path of the file to import.
            overwrite (bool): if True, overwrite existing objects.
            passwords (dict): passwords for database connections.

        Returns:
            dict: import result with status.
        """
        data = {"overwrite": json.dumps(overwrite)}
        passwords = {f"databases/{db}.yaml": pwd for db, pwd in (passwords or {}).items()}
        file_name = os.path.split(file_path)[-1]
        file_ext = os.path.splitext(file_name)[-1].lstrip(".").lower()
        with open(file_path, "rb") as f:
            files = {
                "formData": (file_name, f, f"application/{file_ext}"),
                "passwords": (None, json.dumps(passwords), None),
            }
            response = self.client.post(
                self.import_url,
                files=files,
                data=data,
                headers={"Accept": "application/json"},
            )
        return response.json().get("message") == "OK"

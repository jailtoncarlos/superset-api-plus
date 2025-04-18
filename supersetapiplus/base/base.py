"""Base classes."""
import dataclasses
import logging
from abc import abstractmethod
from contextlib import suppress
from enum import Enum
from typing_extensions import Self
from supersetapiplus.base.parse import ParseMixin
from supersetapiplus.client import QueryStringFilter
from supersetapiplus.typing import NotToJson, Optional
from supersetapiplus.utils import dict_hash

logger = logging.getLogger(__name__)

try:
    from functools import cached_property
except ImportError:  # pragma: no cover
    # Python<3.8
    from cached_property import cached_property

import json
import os.path
from pathlib import Path
from typing import List, Union, Dict, get_args, get_origin, Any, Literal, MutableMapping

import yaml
from requests import HTTPError

from supersetapiplus.exceptions import BadRequestError, ComplexBadRequestError, MultipleFound, NotFound, \
    LoadJsonError, ValidationError


class ObjectField(dataclasses.Field):
    def __init__(self, cls, dict_left:bool=False, dict_right:bool=False, *args, **kwargs):
        kwargs['default'] = kwargs.get('default', dataclasses.MISSING)
        kwargs['default_factory'] = kwargs.get('default_factory', dataclasses.MISSING)
        kwargs['init'] = kwargs.get('init', True)
        kwargs['repr'] = kwargs.get('repr', True)
        kwargs['compare'] = kwargs.get('compare', True)
        kwargs['metadata'] = kwargs.get('metadata', None)
        kwargs['hash'] = kwargs.get('hash', None)
        super().__init__(*args, **kwargs)

        self.cls = cls
        self.dict_left = dict_left
        self.dict_right = dict_right


class ObjectDecoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return str(obj.value)  # Converte o Enum para seu valor (string)
        return super(self).default(obj)


def json_field(**kwargs):
    if not kwargs.get('default'):
        kwargs['default']=None

    return dataclasses.field(repr=False, **kwargs)

def default_string(**kwargs):
    if not kwargs.get('default'):
        kwargs['default']=''
    return dataclasses.field(repr=False, **kwargs)

def default_bool(**kwargs):
    if not kwargs.get('default'):
        kwargs['default']=False
    return dataclasses.field(repr=False)

def raise_for_status(response):
    try:
        response.raise_for_status()
    except HTTPError as e:
        # Attempt to propagate the server error message
        try:
            error_msg = response.json()["message"]
        except Exception:
            try:
                errors = response.json()["errors"]
            except Exception:
                raise e
            raise ComplexBadRequestError(*e.args, request=e.request, response=e.response, errors=errors) from None
        raise BadRequestError(*e.args, request=e.request, response=e.response, message=error_msg) from None


class Object(ParseMixin):
    _factory = None
    JSON_FIELDS = []

    _extra_fields: Dict = {}

    def __post_init__(self):
        for f in self.JSON_FIELDS:
            value = getattr(self, f) or "{}"
            if isinstance(value, str):
                setattr(self, f, json.loads(value))

        # Loop through the fields
        for field in self.fields():
            # If there is a default and the value of the field is none we can assign a value
            if not isinstance(field.default, dataclasses._MISSING_TYPE) \
                    and getattr(self, field.name) is None \
                    and not get_origin(field.type) is Optional:
                        setattr(self, field.name, field.default)

    @abstractmethod
    def validate(self, data: dict):
        pass

    @property
    def extra_fields(self):
        return self._extra_fields

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        dict_self = vars(self)
        dict_self.pop('_extra_fields', None)
        dict_other = vars(other)
        dict_other.pop('_extra_fields', None)
        return dict_self == dict_other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        dict_self = vars(self)
        dict_self.pop('_extra_fields', None)
        return dict_hash(dict_self)

    @classmethod
    def fields(cls) -> set:
        """Get field names."""
        _fields = set()

        for n, f in cls.__dataclass_fields__.items():
            if isinstance(f, dataclasses.Field):
                _fields.add(f)

        _fields.update(dataclasses.fields(cls))

        return _fields

    @classmethod
    def get_field(cls, name):
        for f in cls.fields():
            if f.name == name:
                return f

    @classmethod
    def field_names(cls) -> list:
        """Get field names."""
        fields = []
        for f in cls.fields():
            if not isinstance(f.default, Object):
                fields.append(f.name)
        return fields

    @classmethod
    def required_fields(cls, data) -> dict:
        rdata = {}
        for f in cls.fields():
            if f.default is dataclasses.MISSING and not isinstance(f.default, Object):
                rdata[f.name] = data.get(f.name)
        return rdata

    @classmethod
    def __get_extra_fields(cls, data:dict) -> dict:
        if not data:
            return {}

        field_names = set(cls.field_names())

        data_keys = set(data.keys())
        extra_fields_keys = data_keys - field_names
        extra_fields = {}
        for field_name in extra_fields_keys:
            extra_fields[field_name] = data.pop(field_name)

        return extra_fields

    @classmethod
    def _subclass_object(cls, field: dataclasses.Field):
        if hasattr(field, 'cls'):
            return field.cls
        return None

    @classmethod
    def from_json(cls, data: dict) -> Self:
        extra_fields = cls.__get_extra_fields(data)
        field_name = None
        data_value = None
        try:
            # if not isinstance(data, dict):
            #     return data

            obj = cls(**data)

            for field_name in cls.JSON_FIELDS:
                data_value = data.get(field_name)
                if isinstance(data_value, str):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    if ObjectClass:
                        value = ObjectClass.from_json(json.loads(data[field_name]))
                    else:
                        value = json.loads(data[field_name])

                    setattr(obj, field_name, value)

            for field_name, data_value in data.items():
                logger.debug(f'field_name: {field_name}; data_value: {data_value}')
                if field_name in cls.JSON_FIELDS:
                    continue
                if isinstance(data_value, dict):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    value = None
                    if ObjectClass and field.dict_right:
                        value = {}
                        for k, field_value in data_value.items():
                            value[k] = ObjectClass.from_json(field_value)
                    elif ObjectClass:
                        value = ObjectClass.from_json(data_value)
                    else:
                        value = data_value
                    setattr(obj, field_name, value)
                elif isinstance(data_value, list):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    value = []
                    for field_value in data_value:
                        if ObjectClass and isinstance(field_value, dict):
                            try:
                                value.append(ObjectClass.from_json(field_value))
                            except Exception as err:
                                msg = f"""unhandled exception: {err}
                                    cls={cls}
                                    field_name={field_name}
                                    data_value={data_value}
                                    data={data}
                                    extra_fields={extra_fields}
                                """
                                logger.warning(msg)
                        else:
                            value.append(field_value)
                    setattr(obj, field_name, value)
                else:
                    setattr(obj, field_name, data_value)

            obj._extra_fields = extra_fields
        except Exception as err:
            msg = f"""{err}
                cls={cls}
                field_name={field_name}
                data_value={data_value}
                data={data}
                extra_fields={extra_fields}
            """
            logger.exception(msg)
            raise LoadJsonError(err)
        return obj

    @classmethod
    def remove_exclude_keys(cls, data, parent_field_name=''):
        def is_exclude(field_name, parent_field, data):
            field = cls.get_field(field_name)
            _is_exclude = False
            try:
                if not field and parent_field:
                    ObjectClass = cls._subclass_object(parent_field)
                    field = ObjectClass.get_field(field_name)
                if get_origin(field.type) is Optional:
                    if not data[field.name] and field.default is dataclasses.MISSING:
                        _is_exclude = True
                    elif field.default == data[field.name]:
                        _is_exclude = True
                    else:
                        _is_exclude = False
                if get_origin(field.type) is NotToJson:
                    _is_exclude = True
            except Exception:
                pass
            return _is_exclude

        if isinstance(data, list):
            # If it is a list, we apply the function to each element in the list
            newdata = []
            for item in data:
                if not is_exclude(parent_field_name, parent_field_name, data):
                    newdata.append(cls.remove_exclude_keys(item, parent_field_name))
            return newdata
        if isinstance(data, dict):
            # If it's a dictionary, we loop through its keys and values
            return {
                key: cls.remove_exclude_keys(value, key) for key, value in data.items()
                if not is_exclude(key, cls.get_field(parent_field_name), data)
            }
        # If it is neither a list nor a dictionary, we return the value as is
        return data

    def to_dict(self, columns=[]) -> dict:
        def prepare_value_tuple(field_value):
            values_data = []
            if isinstance(field_value, tuple):
                l1 = field_value[0]
                l2 = field_value[1]
                if isinstance(field_value[0], Object):
                    l1 = field_value[0].to_dict()
                elif isinstance(field_value[1], Object):
                    l2 = field_value[1].to_dict()
                elif isinstance(field_value[0], Enum):
                    l1 = str(field_value[0])
                elif isinstance(field_value[1], Enum):
                    l2 = str(field_value[0])
                values_data.append((l1, l2))
            return values_data

        columns_names = set(columns or [])
        columns_names.update(self.field_names())
        data = {}
        for c in columns_names:
            if not hasattr(self, c):
                # Column that is not implemented yet
                continue
            value = getattr(self, c)
            if isinstance(value, Enum):
                value = str(value)
            elif value and isinstance(value, Object):
                value = value.to_dict(columns)
            elif value and isinstance(value, list):
                values_data = []
                for field_value in value:
                    if isinstance(field_value, Object):
                        values_data.append(field_value.to_dict())
                    elif isinstance(field_value, tuple):
                        values_data = prepare_value_tuple(field_value)
                    elif isinstance(field_value, Enum):
                        values_data.append(str(field_value))
                    else:
                        values_data.append(field_value)
                    value = values_data
            elif value and isinstance(value, dict):
                field = self.get_field(c)
                ObjectClass = self._subclass_object(field)
                if ObjectClass:
                    _value = {}
                    if field.dict_left:
                        for obj, value_ in value.items():
                            _value[obj.to_dict()] = value_
                    elif field.dict_right:
                        for k, obj in value.items():
                            _value[k] = obj.to_dict()
                    value = _value
            elif value and isinstance(value, tuple):
                value = prepare_value_tuple(field_value)
            data[c] = value
            # logger.debug(f'return data {data}')
        return data

#    dictionary = {'fruit': {"Grapes": "10", "color": "green"}, 'vegetable': {"chilli": "4", "color": "red"},}
#    json.dumps(dictionary, indent=3)
#    obj.to_json()
#   json.dumps(self.to_dict(columns), indent=3)
#   print(json.dumps(self.to_dict(columns), indent=3))

    def to_json(self, columns=[]) -> dict:
        data = self.to_dict(columns)
        self.validate(data)

        for field in self.JSON_FIELDS:
            obj = getattr(self, field)
            if isinstance(obj, Object):
                data[field] = json.dumps(obj.to_json(), cls=ObjectDecoder)
            elif isinstance(obj, dict):
                data[field] = json.dumps(data[field], cls=ObjectDecoder)

        copydata = self.remove_exclude_keys(data)

        if copydata.get('extra_fields'):
            copydata.pop('extra_fields')
        logger.debug(f'return data {copydata}')
        return copydata

    @property
    def base_url(self) -> str:
        return self._factory.client.join_urls(self._factory.base_url, self.id)

    def export(self, path: Union[Path, str]) -> None:
        """Export object to path"""
        self._factory.export(ids=[self.id], path=path)

    def fetch(self) -> None:
        """Fetch additional object information."""
        field_names = self.field_names()

        client = self._factory.client
        response = client.get(self.base_url)
        o = response.json().get("result")
        for k, v in o.items():
            if k in field_names:
                if k in self.JSON_FIELDS:
                    setattr(self, k, json.loads(v or "{}"))
                else:
                    setattr(self, k, v)

    def save(self) -> None:
        """Save object information."""
        o = self.to_json(columns=self._factory.edit_columns)
        logger.info(f'payload: {o}')

        response = self._factory.client.put(self.base_url, json=o)
        raise_for_status(response)
        logger.info(f'response: {response.json()}')

    def delete(self) -> bool:
        return self._factory.delete(id=self.id)

    def get_request_response(self):
        jdict = self._request_response.json()
        for field_name in self.JSON_FIELDS:
            jdict['result'][field_name] = json.loads(jdict['result'][field_name])
        return jdict


class ObjectFactories:
    endpoint = ""
    base_object: Object = None

    _INFO_QUERY = {"keys": ["add_columns", "edit_columns"]}

    def __init__(self, client):
        """Create a new Dashboards endpoint.

        Args:
            client (client): superset client
        """
        self.client = client

    @abstractmethod
    def get_base_object(self, data):
        logger.error(f'Abstract Method "get_base_object" not implemented, self: {self}')
        raise NotImplemented()

    @cached_property
    def _infos(self):
        # Get infos
        response = self.client.get(self.info_url, params={"q": json.dumps(self._INFO_QUERY)})
        raise_for_status(response)
        return response.json()

    @property
    def add_columns(self):
        return [e.get("name") for e in self._infos.get("add_columns", [])]

    @property
    def edit_columns(self):
        return [e.get("name") for e in self._infos.get("edit_columns", [])]

    @property
    def base_url(self):
        """Base url for these objects."""
        url = self.client.join_urls(self.client.base_url, self.endpoint)
        logger.info(f'url: {url}')
        return url

    @property
    def info_url(self):
        return self.client.join_urls(self.base_url, "_info")

    @property
    def import_url(self):
        return self.client.join_urls(self.base_url, "import/")

    @property
    def export_url(self):
        return self.client.join_urls(self.base_url, "export/")

    def get(self, id: str):
        """Get an object by id."""
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')

        response = self.client.get(url)
        raise_for_status(response)

        result = response.json()
        logger.info(f'response: {result}')

        data_result = result['result']

        data_result["id"] = result.get('id', data_result.get('id', id))
        BaseClass = self.get_base_object(data_result)

        object = BaseClass.from_json(data_result)
        object._request_response = response
        object._factory = self

        return object

    def find(self, filter:QueryStringFilter, columns:List[str]=[], page_size: int = 100, page: int = 0):
        """Find and get objects from api."""

        response = self.client.find(self.base_url, filter, columns, page_size, page)

        objects = []
        for data in response.get("result"):
            o = self.get_base_object(data).from_json(data)
            o._factory = self
            objects.append(o)

        return objects

    def count(self):
        """Count objects."""
        response = self.client.get(self.base_url)
        raise_for_status(response)
        return response.json()["count"]

    def find_one(self, filter:QueryStringFilter, columns:List[str]=[]):
        """Find only object or raise an Exception."""
        objects = self.find(filter, columns)
        if len(objects) == 0:
            raise NotFound(f"No {self.get_base_object().__name__} found")
        if len(objects) > 1:
            raise MultipleFound(f"Multiple {self.get_base_object().__name__} found")
        return objects[0]

    def add(self, obj) -> int:
        """Create an object on remote."""
        o = obj.to_json(columns=self.add_columns)
        logger.info(f'payload: {o}')

        response = self.client.post(self.base_url, json=o)
        raise_for_status(response)
        result = response.json()
        logger.info(f'response: {result}')

        obj.id = result.get("id")
        obj._factory = self
        return obj.id

    def export(self, ids: List[int], path: Union[Path, str]) -> None:
        """Export object into an importable file"""
        ids_array = ",".join([str(i) for i in ids])
        response = self.client.get(self.export_url, params={"q": f"[{ids_array}]"})

        raise_for_status(response)

        content_type = response.headers["content-type"].strip()
        if content_type.startswith("application/text"):  # pragma: no cover
            # Superset 1.x
            data = yaml.load(response.text, Loader=yaml.FullLoader)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)
            return
        if content_type.startswith("application/json"):  # pragma: no cover
            # Superset 1.x
            data = response.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return
        if content_type.startswith("application/zip"):
            data = response.content
            with open(path, "wb") as f:
                f.write(data)
            return
        raise ValueError(f"Unknown content type {content_type}")

    def delete(self, id: int) -> bool:
        """Delete a object on remote."""
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')
        response = self.client.delete(url)
        raise_for_status(response)
        logger.info(f'response: {response.json()}')
        return response.json().get("message") == "OK"

    def import_file(self, file_path, overwrite=False, passwords=None) -> dict:
        """Import a file on remote.

        :param file_path: Path to a JSON or ZIP file containing the import data
        :param overwrite: If True, overwrite existing remote entities
        :param passwords: JSON map of passwords for each featured database in
        the file. If the ZIP includes a database config in the path
        databases/MyDatabase.yaml, the password should be provided in the
        following format: {"MyDatabase": "my_password"}
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
        raise_for_status(response)

        # If import is successful, the following is returned: {'message': 'OK'}
        return response.json().get("message") == "OK"

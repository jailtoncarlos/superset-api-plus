"""Repositories: CRUD of each REST resource over the HTTP client (search, read, write, export/import)."""
import json
import logging
import os.path
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any, Protocol

import requests
import yaml

from supersetapiplus.core.masking import mask_data
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.exceptions import MultipleFound, NotFound, UnsupportedTypeError
from supersetapiplus.query_string import QueryStringFilter

logger = logging.getLogger(__name__)


class HttpClient(Protocol):
    """What a repository needs from SupersetClient (a protocol: resources must not import the client layer)."""
    @property
    def base_url(self) -> str: ...

    def get(self, url: str, **kwargs: Any) -> requests.Response: ...

    def post(self, url: str, **kwargs: Any) -> requests.Response: ...

    def put(self, url: str, **kwargs: Any) -> requests.Response: ...

    def delete(self, url: str, **kwargs: Any) -> requests.Response: ...

    def find(self, url: str, filter: QueryStringFilter, columns: list[str] | None = None, page_size: int = 100,
             page: int = 0, order_column: str | None = None,
             order_direction: str | None = None) -> requests.Response: ...

    def join_urls(self, *args: Any) -> str: ...


class UnsupportedObject:
    """Listing item whose type has no model in the library (e.g. an unsupported viz_type).

    Returned by `find()` so that a single unknown item does not break the whole listing.
    Exposes the received fields as attributes (`id`, `slice_name`, `viz_type`...) and the original
    dict in `data`. It is read-only: it has no `save()`; `get(id)` on the same item raises
    `UnsupportedTypeError`.
    """

    def __init__(self, data: dict[str, Any], factory: Any = None) -> None:
        self.data = dict(data)
        self.__dict__.update(self.data)
        self._factory = factory

    def __repr__(self) -> str:
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
    # Column whose value selects the model class of a listing item (None: a single class).
    TYPE_COLUMN: str | None = None
    _INFO_QUERY = {"keys": ["add_columns", "edit_columns"]}

    def __init__(self, client: HttpClient) -> None:
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

    def get_base_object(self, data: dict[str, Any] | None = None) -> type[SerializableModel]:
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
        base = self._default_object_class()
        if type_ and hasattr(base, 'for_viz_type'):
            resolved: type[SerializableModel] = base.for_viz_type(type_)  # e.g. Chart subclasses
            return resolved
        return self._default_object_class()

    @cached_property
    def _infos(self) -> dict[str, Any]:
        """
        Get endpoint meta-information, such as the columns available for adding and editing.

        Returns:
            dict: data returned by the /_info endpoint.
        """
        response = self.client.get(self.info_url, params={"q": json.dumps(self._INFO_QUERY)})
        infos: dict[str, Any] = response.json()
        return infos

    @property
    def add_columns(self) -> list[str]:
        """Columns available for adding."""
        return [e.get("name") for e in self._infos.get("add_columns", [])]

    @property
    def edit_columns(self) -> list[str]:
        """Columns available for editing."""
        return [e.get("name") for e in self._infos.get("edit_columns", [])]

    @property
    def base_url(self) -> str:
        """Return the base URL of the current endpoint."""
        url = self.client.join_urls(self.client.base_url, self.endpoint)
        logger.info(f'url: {url}')
        return url

    @property
    def info_url(self) -> str:
        """URL to get information about the endpoint schema."""
        return self.client.join_urls(self.base_url, "_info")

    @property
    def import_url(self) -> str:
        """URL for importing objects."""
        return self.client.join_urls(self.base_url, "import/")

    @property
    def export_url(self) -> str:
        """URL for exporting objects."""
        return self.client.join_urls(self.base_url, "export/")

    def object_url(self, id: int | str | None) -> str:
        return self.client.join_urls(self.base_url, id)

    def fetch(self, obj: SerializableModel) -> None:
        """Reload the fields of `obj` from Superset (JSON text fields are decoded)."""
        result = self.client.get(self.object_url(getattr(obj, "id", None))).json().get("result")
        field_names = obj.field_names()
        for key, value in result.items():
            if key in field_names:
                setattr(obj, key, json.loads(value or "{}") if key in obj.JSON_FIELDS else value)

    def save(self, obj: SerializableModel) -> None:
        """PUT the update-accepted fields of `obj`.

        /_info cannot be used as a filter: in Superset 6.1.0 ChartRestApi declares edit_columns = ['slice_name']
        but validates the body with ChartPutSchema, which requires/accepts datasource_id, params, query_context...
        """
        payload = obj.to_json(columns=list(obj.PUT_FIELDS or []))
        payload.pop("id", None)
        logger.debug('payload: %s', mask_data(payload))
        response = self.client.put(self.object_url(getattr(obj, "id", None)), json=payload)
        logger.debug('response: %s', mask_data(response.json()))

    def get(self, id: int | str) -> Any:
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
             order_column: str | None = None, order_direction: str | None = None) -> list[Any]:
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
        # The class of each item comes from its type column (viz_type for charts): a listing restricted to
        # other columns would leave nothing to choose the class from.
        if columns and self.TYPE_COLUMN and self.TYPE_COLUMN not in columns:
            columns = [*columns, self.TYPE_COLUMN]
        response = self.client.find(self.base_url, filter, columns, page_size, page, order_column, order_direction)
        data_result = response.json()

        objects: list[Any] = []
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
                 page_size: int = 100, order_column: str | None = None,
                 order_direction: str | None = None) -> list[Any]:
        """Find across all pages; same parameters as `find`."""
        filter = filter or QueryStringFilter()
        objects: list[Any] = []
        page = 0
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
            response = self.client.get(self.base_url)
        else:
            response = self.client.find(self.base_url, filter, ["id"], page_size=1)
        count: int = response.json()["count"]
        return count

    def find_one(
            self,
            filter: QueryStringFilter,
            columns: list[str] | None = None,
            full: bool = False,
    ) -> Any:
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

    def add(self, obj: Any) -> int:
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
        new_id: int = obj.id
        return new_id

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
            data = yaml.safe_load(response.text)
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
        return bool(response.json().get("message") == "OK")

    def delete_many(self, ids: list[int]) -> bool:
        """Remove several objects in one request (``DELETE /{resource}/?q=!(ids)``)."""
        if not ids:
            return True
        response = self.client.delete(self.base_url, params={"q": f"!({','.join(str(int(i)) for i in ids)})"})
        logger.debug('response: %s', mask_data(response.json()))
        return bool(response.ok)

    def import_file(self, file_path: str | Path, overwrite: bool = False, passwords: dict[str, str] | None = None,
                    ssh_tunnel_passwords: dict[str, str] | None = None,
                    ssh_tunnel_private_keys: dict[str, str] | None = None,
                    ssh_tunnel_private_key_passwords: dict[str, str] | None = None) -> bool:
        """
        Import a file (JSON or ZIP) into Superset.

        Args:
            file_path (str | Path): path of the file to import.
            overwrite (bool): if True, overwrite existing objects.
            passwords (dict): passwords for database connections, by database name.
            ssh_tunnel_passwords, ssh_tunnel_private_keys, ssh_tunnel_private_key_passwords (dict): SSH tunnel
                secrets of the databases, by database name (form fields of the import endpoints, 6.1.0).

        Returns:
            bool: True when Superset answers "OK".
        """
        data = {"overwrite": json.dumps(overwrite)}
        for name, secrets in (("ssh_tunnel_passwords", ssh_tunnel_passwords),
                              ("ssh_tunnel_private_keys", ssh_tunnel_private_keys),
                              ("ssh_tunnel_private_key_passwords", ssh_tunnel_private_key_passwords)):
            if secrets:
                data[name] = json.dumps({f"databases/{db}.yaml": value for db, value in secrets.items()})
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
        return bool(response.json().get("message") == "OK")


# Name used by the package reorganization (issue #318); ApiModelFactories stays as the public name.
Repository = ApiModelFactories

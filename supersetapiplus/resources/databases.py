"""Databases."""
import warnings
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.types import ConfigurationMethod
from supersetapiplus.core.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.resources.repository import ApiModelFactories


def _given(value: Any) -> bool:
    """Set by the caller: neither the default (None) nor absent from the JSON read (MissingField)."""
    return value is not None and not isinstance(value, MissingField)


class Database(ApiModel):
    """A database connection (`sqlalchemy_uri` or dynamic-form `parameters`) and its SQL Lab permissions."""
    JSON_FIELDS: ClassVar[list[str]] = [
        "extra",
    ]
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    # Fields accepted by the API (OpenAPI 6.1.0: DatabaseRestApi.post / DatabaseRestApi.put).
    POST_FIELDS: ClassVar[tuple[str, ...]] = (
        "allow_ctas", "allow_cvas", "allow_dml", "allow_file_upload", "allow_run_async", "cache_timeout",
        "configuration_method", "database_name", "driver", "engine", "expose_in_sqllab", "external_url",
        "extra", "force_ctas_schema", "impersonate_user", "is_managed_externally", "masked_encrypted_extra",
        "parameters", "server_cert", "sqlalchemy_uri", "ssh_tunnel", "uuid",
    )
    PUT_FIELDS: ClassVar[tuple[str, ...]] = (
        "allow_ctas", "allow_cvas", "allow_dml", "allow_file_upload", "allow_run_async", "cache_timeout",
        "configuration_method", "database_name", "driver", "engine", "expose_in_sqllab", "external_url",
        "extra", "force_ctas_schema", "impersonate_user", "is_managed_externally", "masked_encrypted_extra",
        "parameters", "server_cert", "sqlalchemy_uri", "ssh_tunnel", "uuid",
    )

    database_name: str
    id: int | None = None
    # Same defaults as Superset (models/core.py): DML, CTAS/CVAS and async execution only when
    # explicitly requested (they used to be True, allowing INSERT/UPDATE/DELETE in SQL Lab).
    allow_ctas: bool = False
    allow_cvas: bool = False
    allow_dml: bool = False
    allow_run_async: bool = False
    expose_in_sqllab: bool = True
    engine: str = ''
    extra: dict[str, Any] = Field(default_factory=dict, repr=False)  # JSON text in the API
    force_ctas_schema: str = ''
    server_cert: str = ''
    sqlalchemy_uri: str = ''
    allow_file_upload: SerializableOptional[bool] = None
    cache_timeout: SerializableOptional[int] = None
    configuration_method: SerializableOptional[ConfigurationMethod] = None
    driver: SerializableOptional[str] = None
    impersonate_user: SerializableOptional[bool] = None
    # Secrets of the connection as JSON text (GET returns them masked; send only to change them).
    masked_encrypted_extra: SerializableOptional[str] = None
    parameters: SerializableOptional[dict[str, Any]] = None  # dynamic_form connection parameters
    ssh_tunnel: SerializableOptional[dict[str, Any]] = None
    uuid: SerializableOptional[str] = None
    external_url: SerializableOptional[str] = None
    is_managed_externally: SerializableOptional[bool] = None
    # Deprecated: not accepted by Superset 6.1.0 (DatabaseRestApi.post/put); never sent.
    encrypted_extra: SerializableNotToJson[str | None] = None
    allow_multi_schema_metadata_fetch: SerializableNotToJson[bool | None] = None

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        if _given(self.encrypted_extra):
            warnings.warn("Database.encrypted_extra is deprecated: Superset 6 takes masked_encrypted_extra.",
                          DeprecationWarning, stacklevel=3)
            if not _given(self.masked_encrypted_extra):
                self.masked_encrypted_extra = self.encrypted_extra
        if _given(self.allow_multi_schema_metadata_fetch):
            warnings.warn("Database.allow_multi_schema_metadata_fetch no longer exists in Superset 6 and is "
                          "ignored.", DeprecationWarning, stacklevel=3)

    def to_json(self, columns: list[str] | None = None) -> dict[str, Any]:
        if not self.extra:
            self.extra = {
                "metadata_params": {},
                "engine_params": {},
                "metadata_cache_timeout": {},
                "schemas_allowed_for_csv_upload": [],
            }
        return super().to_json(columns)

    def run(self, query: str, query_limit: int | None = None) -> Any:
        return self._repository().client.run(database_id=self.id, query=query, query_limit=query_limit)

    def test_connection(self) -> bool:
        return bool(self._repository().test_connection(self))


class Databases(ApiModelFactories):
    """Repository of databases (`client.databases`): CRUD, connection test and SQL execution."""
    endpoint = "database/"

    @property
    def test_connection_url(self) -> str:
        """Base url for these objects."""
        url: str = self.client.join_urls(self.client.base_url, self.endpoint, "test_connection/")
        return url

    def test_connection(self, obj: Database) -> bool:
        """Test connection to a database"""
        url = self.test_connection_url
        connection_columns = ["database_name", "sqlalchemy_uri"]
        o = {c: getattr(obj, c) for c in connection_columns}
        response = self.client.post(url, json=o)
        return bool(response.json().get("message") == "OK")

    def _default_object_class(self) -> type[ApiModel]:
        return Database

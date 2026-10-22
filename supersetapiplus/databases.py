"""Databases."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, SerializableModel
from supersetapiplus.base.fields import default_string, json_field


@dataclass
class Database(SerializableModel):
    JSON_FIELDS = [
        "extra",
    ]
    PRESERVE_EXTRA_FIELDS = False
    # Fields accepted by the API (OpenAPI 6.1.0: DatabaseRestApi.post / DatabaseRestApi.put).
    POST_FIELDS = (
        "allow_ctas", "allow_cvas", "allow_dml", "allow_file_upload", "allow_run_async", "cache_timeout",
        "configuration_method", "database_name", "driver", "engine", "expose_in_sqllab", "external_url",
        "extra", "force_ctas_schema", "impersonate_user", "is_managed_externally", "masked_encrypted_extra",
        "parameters", "server_cert", "sqlalchemy_uri", "ssh_tunnel", "uuid",
    )
    PUT_FIELDS = (
        "allow_ctas", "allow_cvas", "allow_dml", "allow_file_upload", "allow_run_async", "cache_timeout",
        "configuration_method", "database_name", "driver", "engine", "expose_in_sqllab", "external_url",
        "extra", "force_ctas_schema", "impersonate_user", "is_managed_externally", "masked_encrypted_extra",
        "parameters", "server_cert", "sqlalchemy_uri", "ssh_tunnel", "uuid",
    )

    database_name: str
    id: int | None = field(default=None)
    # Same defaults as Superset (models/core.py): DML, CTAS/CVAS and async execution only when
    # explicitly requested (they used to be True, allowing INSERT/UPDATE/DELETE in SQL Lab).
    allow_ctas: bool = False
    allow_cvas: bool = False
    allow_dml: bool = False
    allow_multi_schema_metadata_fetch: bool = True
    allow_run_async: bool = False
    expose_in_sqllab: bool = True
    encrypted_extra: str = default_string()
    engine: str = default_string()
    extra: dict = json_field()
    force_ctas_schema: str = default_string()
    server_cert: str = default_string()
    sqlalchemy_uri: str = default_string()

    def to_json(self, columns: list = None) -> dict:
        if not self.extra:
            self.extra = {
                "metadata_params": {},
                "engine_params": {},
                "metadata_cache_timeout": {},
                "schemas_allowed_for_csv_upload": [],
            }
        return super().to_json(columns)

    def run(self, query, query_limit=None):
        return self._factory.client.run(database_id=self.id, query=query, query_limit=query_limit)

    def test_connection(self):
        return self._factory.test_connection(self)


class Databases(ApiModelFactories):
    endpoint = "database/"

    @property
    def test_connection_url(self):
        """Base url for these objects."""
        return self.client.join_urls(self.client.base_url, self.endpoint, "test_connection/")

    def test_connection(self, obj):
        """Test connection to a database"""
        url = self.test_connection_url
        connection_columns = ["database_name", "sqlalchemy_uri"]
        o = {c: getattr(obj, c) for c in connection_columns}
        response = self.client.post(url, json=o)
        return response.json().get("message") == "OK"

    def _default_object_class(self) -> type[SerializableModel]:
        return Database

"""Saved queries."""
from typing import Any, ClassVar

from typing_extensions import Self

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.resources.repository import ApiModelFactories
from supersetapiplus.resources.schema_field import SchemaFieldMixin


class SavedQuery(SchemaFieldMixin):
    """A query saved in SQL Lab (label, SQL, database and schema)."""
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    # Fields accepted by the API (OpenAPI 6.1.0: SavedQueryRestApi.post / SavedQueryRestApi.put).
    POST_FIELDS: ClassVar[tuple[str, ...]] = (
        "catalog", "db_id", "description", "extra_json", "label", "schema", "sql", "template_parameters",
    )
    PUT_FIELDS: ClassVar[tuple[str, ...]] = (
        "catalog", "db_id", "description", "extra_json", "label", "schema", "sql", "template_parameters",
    )

    label: str
    id: int | None = None
    description: str = ''
    sql: str = ''
    db_id: int | None = None
    catalog: SerializableOptional[str] = None
    template_parameters: SerializableOptional[str] = None  # JSON text
    extra_json: SerializableOptional[str] = None  # JSON text

    @classmethod
    def from_json(cls, json: dict[str, Any]) -> Self:
        res = super().from_json(json)
        database = json.get("database")
        if database:
            res.db_id = database.get("id")
        return res

    def run(self, query_limit: int | None = None) -> Any:
        return self._repository().client.run(database_id=self.db_id, query=self.sql, query_limit=query_limit)


class SavedQueries(ApiModelFactories):
    """Repository of saved queries (`client.saved_queries`)."""
    endpoint = "saved_query/"
    base_object = SavedQuery

    def _default_object_class(self) -> type[ApiModel]:
        return SavedQuery

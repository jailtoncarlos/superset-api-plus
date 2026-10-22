"""Saved queries."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, SerializableModel
from supersetapiplus.base.fields import default_string


@dataclass
class SavedQuery(SerializableModel):
    JSON_FIELDS = []
    PRESERVE_EXTRA_FIELDS = False
    # Campos aceitos pela API (OpenAPI 6.1.0: SavedQueryRestApi.post / SavedQueryRestApi.put).
    POST_FIELDS = (
        "catalog", "db_id", "description", "extra_json", "label", "schema", "sql", "template_parameters",
    )
    PUT_FIELDS = (
        "catalog", "db_id", "description", "extra_json", "label", "schema", "sql", "template_parameters",
    )

    label: str
    id: int | None = field(default=None)
    description: str = default_string()
    sql: str = default_string()
    db_id: int = None
    schema: str = default_string()

    @classmethod
    def from_json(cls, json: dict):
        res = super().from_json(json)
        database = json.get("database")
        if database:
            res.db_id = database.get("id")
        return res

    def run(self, query_limit=None):
        return self._factory.client.run(database_id=self.db_id, query=self.sql, query_limit=query_limit)


class SavedQueries(ApiModelFactories):
    endpoint = "saved_query/"
    base_object = SavedQuery

    def _default_object_class(self) -> type[SerializableModel]:
        return SavedQuery

"""Saved queries."""
from dataclasses import dataclass
from typing import Optional, Type

from supersetapiplus.base.base import SerializableModel, ApiModelFactories, default_string


@dataclass
class SavedQuery(SerializableModel):
    JSON_FIELDS = []

    label: str
    id: Optional[int] = None
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

    def _default_object_class(self) -> Type[SerializableModel]:
        return SavedQuery

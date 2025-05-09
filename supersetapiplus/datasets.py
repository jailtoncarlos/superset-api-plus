"""Dashboards."""
from dataclasses import dataclass, field
from typing import Optional, Type

from supersetapiplus.base.base import SerializableModel, ApiModelFactories, QueryStringFilter
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.exceptions import NotFound


@dataclass
class Dataset(SerializableModel):
    JSON_FIELDS = []

    id: Optional[int] = None
    table_name: str = ""
    schema: str = ""
    columns: list = field(default_factory=list)
    description: str = ""
    kind: str = ""
    database_id: Optional[int] = None
    datasource_type: str = ""
    sql: str = ""

    @classmethod
    def from_json(cls, data: dict):
        res = super().from_json(data)
        database = data.get("database")
        if database:
            res.database_id = database.get("id")
        return res

    def to_json(self, *args, **kwargs):
        o = super().to_json(*args, **kwargs)
        o.pop("columns", None)
        if self.id:
            o["database_id"] = self.database_id
        else:
            o["database"] = self.database_id
        return o

    def run(self, query_limit=None):
        if not self.sql:
            raise ValueError("Cannot run a dataset with no SQL")
        return self._factory.client.run(database_id=self.database_id, query=self.sql, query_limit=query_limit)


class Datasets(ApiModelFactories):
    endpoint = "dataset/"

    # list of supported filters
    # http://localhost:8088/api/v1/dataset/_info?q=(keys:!(filters))

    def get_datasource(self, name) -> DataSource:
        filter = QueryStringFilter()
        filter.add('table_name', 'eq', name)
        response = self.client.find(self.base_url, filter, ['id', 'datasource_type'])
        if response.get('result'):
            result = response['result'][0]
            data = {
                'id': result['id'],
                'type': result['datasource_type']
            }
        else:
            raise NotFound(f'Attribut result does not exist in object response.')
        return DataSource(**data)

    def _default_object_class(self) -> Type[SerializableModel]:
        return Dataset

"""Dashboards."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, QueryStringFilter, SerializableModel
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.exceptions import NotFound
from supersetapiplus.query_string import QueryOperator


@dataclass
class Dataset(SerializableModel):
    JSON_FIELDS = []
    PRESERVE_EXTRA_FIELDS = False
    # Campos aceitos pela API (OpenAPI 6.1.0: DatasetRestApi.post / DatasetRestApi.put).
    POST_FIELDS = (
        "always_filter_main_dttm", "catalog", "database", "external_url", "is_managed_externally",
        "normalize_columns", "owners", "schema", "sql", "table_name",
    )
    PUT_FIELDS = (
        "always_filter_main_dttm", "cache_timeout", "catalog", "columns", "database_id", "default_endpoint",
        "description", "external_url", "extra", "fetch_values_predicate", "filter_select_enabled", "folders",
        "is_managed_externally", "is_sqllab_view", "main_dttm_col", "metrics", "normalize_columns", "offset",
        "owners", "schema", "sql", "table_name", "template_params",
    )

    id: int | None = field(default=None)
    table_name: str = ""
    schema: str = ""
    columns: list = field(default_factory=list)
    description: str = ""
    kind: str = ""
    database_id: int | None = None
    datasource_type: str = ""
    sql: str = ""

    @classmethod
    def from_json(cls, data: dict):
        # Lido antes do super(): from_json remove de `data` as chaves que não são campos do modelo.
        database = data.get("database")
        res = super().from_json(data)
        if isinstance(database, dict) and database.get("id"):
            res.database_id = database["id"]
        return res

    def to_json(self, columns: list = None) -> dict:
        o = super().to_json(columns)
        o.pop("columns", None)
        if self.database_id:
            # PUT usa database_id; POST usa database (DatasetRestApi.put / .post).
            o["database_id" if self.id else "database"] = self.database_id
        return o

    def run(self, query_limit=None):
        if not self.sql:
            raise ValueError("Cannot run a dataset with no SQL")
        return self._factory.client.run(database_id=self.database_id, query=self.sql, query_limit=query_limit)


class Datasets(ApiModelFactories):
    endpoint = "dataset/"

    def get_datasource(self, name: str) -> DataSource:
        """DataSource (id e tipo) do dataset com o `table_name` informado."""
        filter = QueryStringFilter()
        filter.add('table_name', QueryOperator.EQUAL, name)
        result = self.client.find(self.base_url, filter, ['id', 'datasource_type']).json().get('result')
        if not result:
            raise NotFound(f"Dataset '{name}' not found.")
        return DataSource(id=result[0]['id'], type=result[0]['datasource_type'])

    def _default_object_class(self) -> type[SerializableModel]:
        return Dataset

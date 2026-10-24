"""Datasets."""
from dataclasses import dataclass, field

from supersetapiplus.base.base import ApiModelFactories, QueryStringFilter, SerializableModel
from supersetapiplus.base.datasource import DataSource
from supersetapiplus.base.types import DatasourceKind, DatasourceType
from supersetapiplus.exceptions import NotFound
from supersetapiplus.query_string import QueryOperator
from supersetapiplus.typing import SerializableOptional


@dataclass
class Dataset(SerializableModel):
    JSON_FIELDS = []
    PRESERVE_EXTRA_FIELDS = False
    # Fields accepted by the API (OpenAPI 6.1.0: DatasetRestApi.post / DatasetRestApi.put).
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

    ID_REFERENCE_FIELDS = ("owners",)
    # Keys of a metric accepted on update (superset/datasets/schemas.py DatasetMetricsPutSchema); GET
    # also returns read-only keys (changed_on, created_on...) that PUT rejects.
    METRIC_FIELDS = ("id", "expression", "description", "extra", "metric_name", "metric_type", "d3format",
                     "currency", "verbose_name", "warning_text", "uuid")

    id: int | None = field(default=None)
    table_name: str = ""
    schema: str = ""
    columns: list = field(default_factory=list)
    description: str = ""
    kind: DatasourceKind | None = None  # read-only: virtual when the dataset has sql
    database_id: int | None = None
    datasource_type: DatasourceType | None = None  # read-only
    sql: str = ""
    # Saved metrics: dicts as Superset returns them (see add_metric); sent with METRIC_FIELDS only.
    metrics: SerializableOptional[list] = field(default=None)
    main_dttm_col: SerializableOptional[str] = field(default=None)
    owners: SerializableOptional[list] = field(default=None)
    catalog: SerializableOptional[str] = field(default=None)
    cache_timeout: SerializableOptional[int] = field(default=None)
    default_endpoint: SerializableOptional[str] = field(default=None)
    extra: SerializableOptional[str] = field(default=None)  # JSON text
    fetch_values_predicate: SerializableOptional[str] = field(default=None)
    template_params: SerializableOptional[str] = field(default=None)  # JSON text
    filter_select_enabled: SerializableOptional[bool] = field(default=None)
    normalize_columns: SerializableOptional[bool] = field(default=None)
    always_filter_main_dttm: SerializableOptional[bool] = field(default=None)
    is_sqllab_view: SerializableOptional[bool] = field(default=None)
    offset: SerializableOptional[int] = field(default=None)
    external_url: SerializableOptional[str] = field(default=None)
    is_managed_externally: SerializableOptional[bool] = field(default=None)

    @classmethod
    def from_json(cls, data: dict):
        # Read before super(): from_json removes from `data` the keys that are not model fields.
        database = data.get("database")
        res = super().from_json(data)
        if isinstance(database, dict) and database.get("id"):
            res.database_id = database["id"]
        return res

    def add_metric(self, metric_name: str, expression: str, verbose_name: str | None = None,
                   d3format: str | None = None, description: str | None = None) -> dict:
        """Saved metric of the dataset (sent on the next save); returns the metric dict."""
        metric = {"metric_name": metric_name, "expression": expression}
        metric.update({key: value for key, value in (("verbose_name", verbose_name), ("d3format", d3format),
                                                     ("description", description)) if value is not None})
        if not isinstance(self.metrics, list):
            self.metrics = []
        self.metrics.append(metric)
        return metric

    def to_json(self, columns: list = None) -> dict:
        o = super().to_json(columns)
        o.pop("columns", None)
        if isinstance(o.get("metrics"), list):
            o["metrics"] = [{key: value for key, value in metric.items() if key in self.METRIC_FIELDS}
                            for metric in o["metrics"]]
        if self.database_id:
            # PUT uses database_id; POST uses database (DatasetRestApi.put / .post).
            o["database_id" if self.id else "database"] = self.database_id
        return o

    def run(self, query_limit=None):
        if not self.sql:
            raise ValueError("Cannot run a dataset with no SQL")
        return self._factory.client.run(database_id=self.database_id, query=self.sql, query_limit=query_limit)


class Datasets(ApiModelFactories):
    endpoint = "dataset/"

    def get_datasource(self, name: str) -> DataSource:
        """DataSource (id and type) of the dataset with the given `table_name`."""
        filter = QueryStringFilter()
        filter.add('table_name', QueryOperator.EQUAL, name)
        result = self.client.find(self.base_url, filter, ['id', 'datasource_type']).json().get('result')
        if not result:
            raise NotFound(f"Dataset '{name}' not found.")
        return DataSource(id=result[0]['id'], type=result[0]['datasource_type'])

    def _default_object_class(self) -> type[SerializableModel]:
        return Dataset

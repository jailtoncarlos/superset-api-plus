"""Datasets."""
from typing import Any, ClassVar

from pydantic import Field
from typing_extensions import Self

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.core.types import DatasourceKind, DatasourceType
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import NotFound, ValidationError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
from supersetapiplus.resources.databases import Database
from supersetapiplus.resources.repository import ApiModelFactories
from supersetapiplus.resources.schema_field import SchemaFieldMixin


class Dataset(SchemaFieldMixin):
    """A dataset: a physical table or a virtual one (`sql`), with its saved metrics and time column."""
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    # Fields accepted by the API (OpenAPI 6.1.0: DatasetRestApi.post / DatasetRestApi.put).
    POST_FIELDS: ClassVar[tuple[str, ...]] = (
        "always_filter_main_dttm", "catalog", "database", "external_url", "is_managed_externally",
        "normalize_columns", "owners", "schema", "sql", "table_name",
    )
    PUT_FIELDS: ClassVar[tuple[str, ...]] = (
        "always_filter_main_dttm", "cache_timeout", "catalog", "columns", "database_id", "default_endpoint",
        "description", "external_url", "extra", "fetch_values_predicate", "filter_select_enabled", "folders",
        "is_managed_externally", "is_sqllab_view", "main_dttm_col", "metrics", "normalize_columns", "offset",
        "owners", "schema", "sql", "table_name", "template_params",
    )

    ID_REFERENCE_FIELDS: ClassVar[tuple[str, ...]] = ("owners",)
    # Keys of a metric accepted on update (superset/datasets/schemas.py DatasetMetricsPutSchema); GET
    # also returns read-only keys (changed_on, created_on...) that PUT rejects.
    METRIC_FIELDS: ClassVar[tuple[str, ...]] = (
        "id", "expression", "description", "extra", "metric_name", "metric_type", "d3format", "currency",
        "verbose_name", "warning_text", "uuid")
    # Keys of a column accepted on update (DatasetColumnsPutSchema); columns are sent only after a change.
    COLUMN_FIELDS: ClassVar[tuple[str, ...]] = (
        "id", "column_name", "type", "advanced_data_type", "verbose_name", "description", "expression", "extra",
        "filterable", "groupby", "is_active", "is_dttm", "python_date_format", "datetime_format", "uuid")

    id: int | None = None
    table_name: str = ""
    columns: list[Any] = Field(default_factory=list)
    description: str = ""
    kind: DatasourceKind | None = None  # read-only: virtual when the dataset has sql
    database_id: int | None = None
    datasource_type: DatasourceType | None = None  # read-only
    sql: str = ""
    # Saved metrics: dicts as Superset returns them (see add_metric); sent with METRIC_FIELDS only.
    metrics: SerializableOptional[list[dict[str, Any]]] = None
    main_dttm_col: SerializableOptional[str] = None
    owners: SerializableOptional[list[Any]] = None
    catalog: SerializableOptional[str] = None
    cache_timeout: SerializableOptional[int] = None
    default_endpoint: SerializableOptional[str] = None
    extra: SerializableOptional[str] = None  # JSON text
    fetch_values_predicate: SerializableOptional[str] = None
    template_params: SerializableOptional[str] = None  # JSON text
    filter_select_enabled: SerializableOptional[bool] = None
    normalize_columns: SerializableOptional[bool] = None
    always_filter_main_dttm: SerializableOptional[bool] = None
    is_sqllab_view: SerializableOptional[bool] = None
    offset: SerializableOptional[int] = None
    external_url: SerializableOptional[str] = None
    is_managed_externally: SerializableOptional[bool] = None
    # Set by add_calculated_column: columns are sent only after a change (not a dataclass field).
    _columns_changed = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        # Read before super(): from_json removes from `data` the keys that are not model fields.
        database = data.get("database")
        res = super().from_json(data)
        if isinstance(database, dict) and database.get("id"):
            res.database_id = database["id"]
        return res

    def add_metric(self, metric_name: str, expression: str, verbose_name: str | None = None,
                   d3format: str | None = None, description: str | None = None) -> dict[str, Any]:
        """Saved metric of the dataset, sent on the next save; a metric with the same name is updated (its id
        is kept). Returns the metric dict. The dataset must be read with ``client.datasets.get`` (see
        :meth:`_stored_list`)."""
        values = {"metric_name": metric_name, "expression": expression, "verbose_name": verbose_name,
                  "d3format": d3format, "description": description}
        return _merge_by_name(self._stored_list("metrics"), "metric_name", values)

    def add_calculated_column(self, column_name: str, expression: str, verbose_name: str | None = None,
                              type: str | None = None, is_dttm: bool | None = None,
                              description: str | None = None) -> dict[str, Any]:
        """Calculated column (a SQL expression) of the dataset, sent on the next save; a calculated column with
        the same name is updated (its id is kept). Returns the column dict. The dataset must be read with
        ``client.datasets.get`` (see :meth:`_stored_list`)."""
        columns = self._stored_list("columns")
        physical = next((c for c in columns if c.get("column_name") == column_name and not c.get("expression")), None)
        if physical is not None:
            raise ValidationError(f"{column_name!r} is a column of the table, not a calculated column.",
                                  solution="Choose another name for the calculated column.")
        values = {"column_name": column_name, "expression": expression, "verbose_name": verbose_name,
                  "type": type, "is_dttm": is_dttm, "description": description}
        self._columns_changed = True
        return _merge_by_name(columns, "column_name", values)

    def _stored_list(self, field_name: str) -> list[dict[str, Any]]:
        """`metrics` or `columns` as read from Superset, to be changed and sent back whole.

        Superset replaces the whole list on update (DatasetDAO.update_metrics/update_columns delete the items
        left out) and does not take it when creating a dataset; only a dataset read with
        ``client.datasets.get`` (the list endpoint does not return them) has the complete list.
        """
        current = getattr(self, field_name)
        if not self.id or not self._read_from_superset or not isinstance(current, list):
            raise ValidationError(f"Read the dataset with client.datasets.get(id) before changing its {field_name}.",
                                  solution=f"Superset replaces all the {field_name} of a dataset on save: the ones "
                                           "not sent are deleted, so the dataset must hold the stored list.")
        return current

    def refresh(self) -> "Dataset":
        """Syncs the columns with the table in the database (PUT /dataset/{pk}/refresh); returns the dataset
        read again."""
        repository = self._repository()
        repository.refresh(self.id)
        refreshed: Dataset = repository.get(self.id)
        return refreshed

    def duplicate(self, table_name: str) -> "Dataset":
        """Copy of this virtual dataset named `table_name` (POST /dataset/duplicate); returns the copy."""
        duplicated: Dataset = self._repository().duplicate(self.id, table_name)
        return duplicated

    def to_json(self, columns: list[str] | None = None) -> dict[str, Any]:
        o = super().to_json(columns)
        o.pop("columns", None)
        if self._columns_changed and isinstance(self.columns, list):  # sent whole, with the update keys only
            o["columns"] = [{key: value for key, value in column.items() if key in self.COLUMN_FIELDS}
                            for column in self.columns]
        if isinstance(o.get("metrics"), list):
            o["metrics"] = [{key: value for key, value in metric.items() if key in self.METRIC_FIELDS}
                            for metric in o["metrics"]]
        if self.database_id:
            # PUT uses database_id; POST uses database (DatasetRestApi.put / .post).
            o["database_id" if self.id else "database"] = self.database_id
        return o

    def run(self, query_limit: int | None = None) -> Any:
        if not self.sql:
            raise ValueError("Cannot run a dataset with no SQL")
        return self._repository().client.run(database_id=self.database_id, query=self.sql, query_limit=query_limit)


class Datasets(ApiModelFactories):
    """Repository of datasets (`client.datasets`): CRUD and `get_datasource()` by table name."""
    endpoint = "dataset/"
    # Body fields of POST /dataset/duplicate and /dataset/get_or_create/ (DatasetDuplicateSchema and
    # GetOrCreateDatasetSchema, superset/datasets/schemas.py 6.1.0; checked in test_enum_conformance.py).
    DUPLICATE_FIELDS = ("base_model_id", "table_name")
    GET_OR_CREATE_FIELDS = ("table_name", "database_id", "catalog", "schema", "template_params",
                            "normalize_columns", "always_filter_main_dttm")

    def get_datasource(self, name: str) -> DataSource:
        """DataSource (id and type) of the dataset with the given `table_name`."""
        filter = QueryStringFilter()
        filter.add('table_name', QueryOperator.EQUAL, name)
        result = self.client.find(self.base_url, filter, ['id', 'datasource_type']).json().get('result')
        if not result:
            raise NotFound(f"Dataset '{name}' not found.")
        return DataSource(id=result[0]['id'], type=result[0]['datasource_type'])

    def refresh(self, dataset_id: int) -> None:
        """Syncs the dataset columns with its table (PUT /dataset/{pk}/refresh)."""
        self.client.put(self.client.join_urls(self.object_url(dataset_id), "refresh"))

    def duplicate(self, dataset_id: int, table_name: str) -> Dataset:
        """Copy of a virtual dataset named `table_name` (POST /dataset/duplicate; Superset rejects physical
        datasets with 422). Returns the copy, read from Superset."""
        url = self.client.join_urls(self.base_url, "duplicate")
        body = dict(zip(self.DUPLICATE_FIELDS, (dataset_id, table_name), strict=True))
        new_id = self.client.post(url, json=body).json()["id"]
        duplicated: Dataset = self.get(new_id)
        return duplicated

    def get_or_create(self, table_name: str, database: Database | int, schema: str | None = None,
                      catalog: str | None = None, **options: str | bool | None) -> Dataset:
        """The dataset of a physical table, created when it does not exist (POST /dataset/get_or_create/).

        `database` is a Database or its id; `options` are the other fields of GetOrCreateDatasetSchema
        (``template_params``, ``normalize_columns``, ``always_filter_main_dttm``). A table missing from the
        database raises UnprocessableEntityError.
        """
        body = {"table_name": table_name, "database_id": database.id if isinstance(database, Database) else database,
                "schema": schema,
                "catalog": catalog, **options}
        unknown = set(body) - set(self.GET_OR_CREATE_FIELDS)
        if unknown:
            raise ValueError(f"get_or_create does not take {sorted(unknown)}; it takes {self.GET_OR_CREATE_FIELDS}.")
        url = self.client.join_urls(self.base_url, "get_or_create/")
        result = self.client.post(url, json={k: v for k, v in body.items() if v is not None}).json()["result"]
        dataset: Dataset = self.get(result["table_id"])
        return dataset

    def _default_object_class(self) -> type[ApiModel]:
        return Dataset


def _merge_by_name(items: list[dict[str, Any]], name_key: str, values: dict[str, Any]) -> dict[str, Any]:
    """Updates the item named like `values` (keeping its id and other keys) or appends a new one."""
    given = {key: value for key, value in values.items() if value is not None}
    item = next((existing for existing in items if existing.get(name_key) == given[name_key]), None)
    if item is None:
        item = {}
        items.append(item)
    item.update(given)
    return item

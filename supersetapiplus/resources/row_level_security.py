"""Row level security rules (/api/v1/rowlevelsecurity/): the SQL clause Superset adds to the queries of some roles."""
from typing import Any, ClassVar

from pydantic import Field, field_validator

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.types import RowLevelSecurityFilterType
from supersetapiplus.resources.repository import ApiModelFactories


def _reference_id(item: object) -> object:
    """A saved object given as a table or role becomes its id; ids and the dicts read from Superset stay as given."""
    if isinstance(item, ApiModel):
        pk = getattr(item, "id", None)
        if pk is None:
            raise ValueError(f"a {type(item).__name__} without id cannot be referenced (save or read it first)")
        return pk
    return item


class RowLevelSecurityRule(ApiModel):
    """A row level security rule (OpenAPI 6.1.0: RLSRestApi.post / .put).

    `clause` is added to the WHERE of every query on `tables`: for the `roles` listed (Regular), or for every role
    except them (Base). Rules sharing a `group_key` are combined with OR, different groups with AND.
    `tables` and `roles` are read as `[{id, schema, table_name}]` and `[{id, name}]`; they accept datasets, roles or
    their ids, and are sent as ids.
    """
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    POST_FIELDS: ClassVar[tuple[str, ...]] = ("name", "filter_type", "tables", "roles", "clause", "group_key",
                                              "description")
    PUT_FIELDS: ClassVar[tuple[str, ...]] = POST_FIELDS
    ID_REFERENCE_FIELDS: ClassVar[tuple[str, ...]] = ("tables", "roles")

    name: str
    filter_type: RowLevelSecurityFilterType
    tables: list[Any]
    clause: str
    roles: list[Any] = Field(default_factory=list)
    id: int | None = None
    group_key: str | None = None
    description: str | None = None

    @field_validator("tables", "roles", mode="before")
    @classmethod
    def _saved_objects_as_ids(cls, value: object) -> object:
        return [_reference_id(item) for item in value] if isinstance(value, (list, tuple)) else value


class RowLevelSecurity(ApiModelFactories):
    """Repository of row level security rules (`client.row_level_security`): CRUD and search, e.g. by `name`."""
    endpoint = "rowlevelsecurity/"

    def _default_object_class(self) -> type[ApiModel]:
        return RowLevelSecurityRule

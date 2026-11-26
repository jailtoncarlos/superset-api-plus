"""Row level security rules (/api/v1/rowlevelsecurity/): the SQL clause Superset adds to the queries of some roles."""
from typing import Any, ClassVar

from pydantic import Field, field_validator

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.types import RowLevelSecurityFilterType, SubjectType
from supersetapiplus.core.typing import SerializableNotToJson
from supersetapiplus.exceptions import NotFound, ValidationError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter
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
    """A row level security rule (OpenAPI 7.0.0rc3: RLSRestApi.post / .put).

    `clause` is added to the WHERE of every query on `tables`: for the `subjects` listed (Regular), or for every user
    except them (Base). Rules sharing a `group_key` are combined with OR, different groups with AND. A Regular rule
    needs at least one subject.

    `tables` and `subjects` are read as `[{id, schema, table_name}]` and `[{id, label, type}]`; they accept datasets,
    subjects or their ids, and are sent as ids. `users` and `roles` take users or roles (objects or ids), sent as
    their subjects (`roles`, the field of Superset 6.1, is deprecated).
    """
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    POST_FIELDS: ClassVar[tuple[str, ...]] = ("name", "filter_type", "tables", "subjects", "clause", "group_key",
                                              "description")
    PUT_FIELDS: ClassVar[tuple[str, ...]] = POST_FIELDS
    ID_REFERENCE_FIELDS: ClassVar[tuple[str, ...]] = ("tables", "subjects")
    SUBJECT_ALIASES: ClassVar[dict[str, tuple[str, SubjectType, bool]]] = {
        "roles": ("subjects", SubjectType.ROLE, True), "users": ("subjects", SubjectType.USER, False)}

    name: str
    filter_type: RowLevelSecurityFilterType
    tables: list[Any]
    clause: str
    subjects: list[Any] = Field(default_factory=list)
    roles: SerializableNotToJson[list[Any]] = Field(default_factory=list)
    users: SerializableNotToJson[list[Any]] = Field(default_factory=list)
    id: int | None = None
    group_key: str | None = None
    description: str | None = None

    @field_validator("tables", "subjects", "roles", "users", mode="before")
    @classmethod
    def _saved_objects_as_ids(cls, value: object) -> object:
        return [_reference_id(item) for item in value] if isinstance(value, (list, tuple)) else value

    def _check_before_sending(self) -> None:
        super()._check_before_sending()
        if self.filter_type == RowLevelSecurityFilterType.REGULAR and not (self.subjects or self.roles or self.users):
            raise ValidationError(message=f"Row level security rule {self.name!r}: a Regular rule needs at least one "
                                          "subject (subjects, users or roles)",
                                  solution="Give the subjects the clause applies to, or make it a Base rule.")


class RowLevelSecurity(ApiModelFactories):
    """Repository of row level security rules (`client.row_level_security`): CRUD and search, e.g. by `name`."""
    endpoint = "rowlevelsecurity/"

    def create_or_update(self, rule: RowLevelSecurityRule) -> int:
        """Create `rule`, or update the rule with its name (Superset keeps rule names unique); returns the rule id.

        Idempotent: running it again with the same rule leaves one rule with the same id and fields. An existing rule
        is replaced by `rule` (PUT of every field, so a `group_key` or `description` left as None is cleared).
        `rule.id` is set, so `rule.save()` and `delete(rule.id)` work afterwards.
        """
        name_filter = QueryStringFilter()
        name_filter.add("name", QueryOperator.EQUAL, rule.name)
        try:
            existing = self.find_one(name_filter, columns=["id", "name"])
        except NotFound:
            return self.add(rule)
        rule.id = existing.id
        rule._factory = self
        self.save(rule)
        return int(existing.id)

    def _default_object_class(self) -> type[ApiModel]:
        return RowLevelSecurityRule

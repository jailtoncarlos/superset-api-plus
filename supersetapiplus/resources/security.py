"""Roles and permissions (Flask-AppBuilder security API: /api/v1/security/roles/ and permissions-resources/)."""
from collections.abc import Iterable
from typing import Any, ClassVar

from typing_extensions import Self

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.exceptions import NotFound
from supersetapiplus.resources.repository import ApiModelFactories


class Permission(ApiModel):
    """A permission on a view menu (FAB's PermissionView), e.g. `can_read` on `Chart`.

    Read from `client.permissions` (`{"permission": {"name"}, "view_menu": {"name"}}`) or from the permissions of a
    role (`{"permission_name", "view_menu_name"}`); both carry the same id, the one a role's permission list takes.
    """
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False

    id: int | None = None
    permission_name: str = ''
    view_menu_name: str = ''

    @classmethod
    def from_json(cls, json: dict[str, Any]) -> Self:
        data = dict(json)
        for nested, flat in (("permission", "permission_name"), ("view_menu", "view_menu_name")):
            value = data.pop(nested, None)
            if isinstance(value, dict):
                data.setdefault(flat, value.get("name", ''))
        return super().from_json(data)

    @property
    def display_name(self) -> str:
        """The name Flask-AppBuilder shows and role files exported from the UI use: `can read on Chart`."""
        return f"{self.permission_name.replace('_', ' ')} on {self.view_menu_name}"


class Role(ApiModel):
    """A role: its name (OpenAPI 6.1.0: SupersetRoleApi.post / .put); its permissions through `permissions()`."""
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    POST_FIELDS: ClassVar[tuple[str, ...]] = ("name",)
    PUT_FIELDS: ClassVar[tuple[str, ...]] = ("name",)

    name: str
    id: int | None = None

    def permissions(self) -> list[Permission]:
        """The permissions of the saved role."""
        result: list[Permission] = self._repository().permissions(self.id)
        return result

    def set_permissions(self, permissions: Iterable[Permission | int]) -> None:
        """Replace the permissions of the saved role (see Roles.set_permissions)."""
        self._repository().set_permissions(self.id, permissions)


class Roles(ApiModelFactories):
    """Repository of roles (`client.roles`): CRUD and search, e.g. by `name`, plus the permissions of a role."""
    endpoint = "security/roles/"

    def _default_object_class(self) -> type[ApiModel]:
        return Role

    def permissions(self, role_id: int | None) -> list[Permission]:
        """The permissions of a role (`GET /security/roles/{id}/permissions/`)."""
        response = self.client.get(self.client.join_urls(self.base_url, role_id, "permissions/"))
        return [Permission.from_json(item) for item in response.json().get("result", [])]

    def set_permissions(self, role_id: int | None, permissions: Iterable[Permission | int]) -> None:
        """Replace the permissions of a role with `permissions` (objects or ids of `client.permissions`).

        Superset replaces the whole list (`POST /security/roles/{id}/permissions`): a permission left out is removed.
        """
        ids = [p if isinstance(p, int) else p.id for p in permissions]
        if any(pk is None for pk in ids):
            raise ValueError("a permission without id cannot be granted (read it from client.permissions)")
        url = self.client.join_urls(self.base_url, role_id, "permissions")
        self.client.post(url, json={"permission_view_menu_ids": ids})


class Permissions(ApiModelFactories):
    """Repository of the permissions on view menus (`client.permissions`); read-only here."""
    endpoint = "security/permissions-resources/"

    def _default_object_class(self) -> type[ApiModel]:
        return Permission

    def find_by_display_names(self, names: Iterable[str]) -> list[Permission]:
        """The permissions with these display names (`can read on Chart`), in the order given.

        Raises:
            NotFound: some name matches no permission of the instance (all of them are listed).
        """
        names = list(names)
        by_name = {p.display_name: p for p in self.iter_all()}
        missing = [n for n in names if n not in by_name]
        if missing:
            raise NotFound(f"No permission named {', '.join(missing)}")
        return [by_name[n] for n in names]

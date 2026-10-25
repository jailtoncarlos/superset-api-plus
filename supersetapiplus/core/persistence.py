"""Persistence facade of the models: methods that delegate to the repository the object is bound to."""
from pathlib import Path
from typing import Any

from supersetapiplus.exceptions import UnboundModelError


class PersistenceMixin:
    """``save()``, ``fetch()``, ``delete()``, ``export()`` and ``base_url`` of a model, delegated to the repository
    (``client.charts``, ``client.dashboards``...) it was read or created through (``_factory``)."""
    _factory: Any

    def _repository(self) -> Any:
        """Repository (``client.charts``, ``client.dashboards``...) the object is bound to."""
        if self._factory is None:
            raise UnboundModelError(
                f"{type(self).__name__} is not bound to a Superset client: create it with client.<resource>.add() "
                "or read it with client.<resource>.get() before calling methods that reach the server.")
        return self._factory

    @property
    def base_url(self) -> str:
        """URL of this object on the REST API."""
        url: str = self._repository().object_url(getattr(self, "id", None))
        return url

    def export(self, path: Path | str) -> None:
        """Export this object to a file (ZIP, JSON or YAML)."""
        self._repository().export(ids=[getattr(self, "id", None)], path=path)

    def fetch(self) -> None:
        """Reload the fields of this object from Superset."""
        self._repository().fetch(self)

    def save(self) -> None:
        """Send the update-accepted fields (PUT_FIELDS) of this object to Superset."""
        self._repository().save(self)

    def delete(self) -> bool:
        """Delete this object from Superset."""
        deleted: bool = self._repository().delete(id=getattr(self, "id", None))
        return deleted

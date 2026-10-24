"""Old public names kept as aliases that emit DeprecationWarning (renames keep the old name working)."""
import warnings
from collections.abc import Callable
from typing import Any


def warn_renamed(old: str, new: str, stacklevel: int = 3) -> None:
    warnings.warn(f"{old} is deprecated; use {new}.", DeprecationWarning, stacklevel=stacklevel)


def module_aliases(module: str, namespace: dict[str, Any], aliases: dict[str, str]) -> Callable[[str], Any]:
    """Module ``__getattr__`` (PEP 562) resolving renamed attributes: ``{old name: new name}``."""
    def __getattr__(name: str) -> Any:
        if name in aliases:
            warn_renamed(f"{module}.{name}", f"{module}.{aliases[name]}")
            return namespace[aliases[name]]
        raise AttributeError(f"module {module!r} has no attribute {name!r}")
    return __getattr__

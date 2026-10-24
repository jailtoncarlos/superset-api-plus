"""Old public names kept as aliases that emit DeprecationWarning (renames keep the old name working)."""
import warnings


def warn_renamed(old: str, new: str, stacklevel: int = 3) -> None:
    warnings.warn(f"{old} is deprecated; use {new}.", DeprecationWarning, stacklevel=stacklevel)


def module_aliases(module: str, namespace: dict, aliases: dict[str, str]):
    """Module ``__getattr__`` (PEP 562) resolving renamed attributes: ``{old name: new name}``."""
    def __getattr__(name: str):
        if name in aliases:
            warn_renamed(f"{module}.{name}", f"{module}.{aliases[name]}")
            return namespace[aliases[name]]
        raise AttributeError(f"module {module!r} has no attribute {name!r}")
    return __getattr__

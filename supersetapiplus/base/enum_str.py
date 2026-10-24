from enum import Enum, EnumMeta

from supersetapiplus.deprecation import warn_renamed

# Renamed enum members: {enum class: {old member name: new member name}} (see deprecate_members).
_RENAMED_MEMBERS: dict[type, dict[str, str]] = {}


class _StringEnumMeta(EnumMeta):
    def __getattr__(cls, name):
        renamed = _RENAMED_MEMBERS.get(cls, {})
        if name in renamed:
            warn_renamed(f"{cls.__name__}.{name}", f"{cls.__name__}.{renamed[name]}")
            return cls[renamed[name]]
        lookup = getattr(super(), "__getattr__", None)  # EnumMeta defines it up to Python 3.11
        if lookup is None:
            raise AttributeError(name)
        return lookup(name)


def deprecate_members(enum_cls: type, renamed: dict[str, str]) -> None:
    """Keeps old member names of `enum_cls` working, with a DeprecationWarning."""
    _RENAMED_MEMBERS[enum_cls] = renamed


class StringEnum(Enum, metaclass=_StringEnumMeta):
    def __str__(self):
        return str(self.value)

    def __eq__(self, other):
        if str(self.__class__) == str(other.__class__):
            return self.value == other.value
        # elif isinstance(other, str):
        #     return self.value == other

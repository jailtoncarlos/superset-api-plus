"""
Module typing.py

Defines generic helper types used to serialize and deserialize objects in `supersetapiplus`.
These types control selective export of attributes and the handling of optional fields
in models that inherit from the base class `SerializableModel`.

Classes:
    NotToJson[T]: generic type wrapping values that must not be serialized
                  into the final JSON (omitted on export).
    Optional[T]: generic type wrapping optional values, with custom logic to drop
                 null or default-valued fields during JSON serialization.

Aliases:
    FilterValue: helper type for the basic types accepted in filters (bool, datetime, float, int, str).
    FilterValues: accepts a single FilterValue, or a list or tuple of them.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Optional, TypeVar, get_args, get_origin

T = TypeVar('T')


class _Marker:
    """Serialization rule attached to a field annotation (``Annotated[X, marker]``)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


#: Left out of the serialized dictionary while unset: None (with a None default) or an empty model default.
OPTIONAL = _Marker("SerializableOptional")
#: Never serialized.
NOT_TO_JSON = _Marker("SerializableNotToJson")


if TYPE_CHECKING:
    # For type checkers the markers are transparent: SerializableOptional[X] is X | None and
    # SerializableNotToJson[X] is X. At runtime they are the classes below, read by the serialization.
    from typing import Optional as SerializableOptional
    from typing import Union as SerializableNotToJson
else:
    class SerializableNotToJson:
        """``SerializableNotToJson[X]``: a field of type X that is never serialized."""

        def __class_getitem__(cls, item: Any) -> Any:
            return Annotated[item, NOT_TO_JSON]


    class SerializableOptional:
        """``SerializableOptional[X]``: an optional field (X | None) left out of the serialized dictionary while
        it is unset, i.e. None with a None default, or a dictionary equal to an empty model default."""

        def __class_getitem__(cls, item: Any) -> Any:
            return Annotated[Optional[item], OPTIONAL]  # noqa: UP045 (item may be a forward-reference string)


def has_marker(annotation: Any, marker: _Marker) -> bool:
    """Whether a field annotation carries a serialization marker (SerializableOptional, SerializableNotToJson)."""
    return get_origin(annotation) is Annotated and marker in get_args(annotation)[1:]


__all__ = ["FilterValue", "FilterValues", "NOT_TO_JSON", "OPTIONAL", "SerializableNotToJson", "SerializableOptional",
           "has_marker"]

#: Helper type for the simple values accepted in filters.
FilterValue = bool | datetime | float | int | str

#: Helper type for multiple filter values (single value, list or tuple).
FilterValues = FilterValue | list[FilterValue] | tuple[FilterValue]

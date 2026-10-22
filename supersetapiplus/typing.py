"""
Module typing.py

Defines generic helper types used to serialize and deserialize objects in `supersetapiplus`.
These types control selective export of attributes and the handling of optional fields
in models that inherit from the base class `Object`.

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
from typing import Generic, TypeVar

T = TypeVar('T')


class SerializableNotToJson(Generic[T]):
    """
    Generic wrapper for a value that **must not be included in JSON serialization**.

    Used in models that inherit from `Object`, together with the logic of
    `remove_exclude_keys`, to automatically drop fields from the output JSON.

    Parameters:
        value (T): wrapped value, used internally but never exported.

    Methods:
        get() -> T:
            Returns the wrapped value.
    """

    def __init__(self, value: T):
        self.value = value

    def get(self) -> T:
        """Return the wrapped value."""
        return self.value


class SerializableOptional(Generic[T]):
    """
    Generic wrapper for an **optional** value, conditionally excluded during JSON serialization.

    Unlike `typing.Optional`, this class lets `remove_exclude_keys` drop the field
    from the JSON output when:
      - the value is `None` and the field has no default; or
      - the value equals the default defined in the dataclass.

    Parameters:
        value (T): wrapped value, possibly optional.

    Methods:
        get() -> T:
            Returns the wrapped value.
    """

    def __init__(self, value: T):
        self.value = value

    def get(self) -> T:
        """Return the wrapped value."""
        return self.value


#: Helper type for the simple values accepted in filters.
FilterValue = bool | datetime | float | int | str

#: Helper type for multiple filter values (single value, list or tuple).
FilterValues = FilterValue | list[FilterValue] | tuple[FilterValue]

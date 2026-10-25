"""JSON encoding of model values: enums as their values (numbers for integer enums)."""
import json
from enum import Enum
from typing import Any


class ObjectDecoder(json.JSONEncoder):
    """
    Custom JSON encoder that serializes objects containing Enum instances.

    Overrides `json.JSONEncoder.default` so that `Enum` values are converted to
    their string representation (usually `value`), making it easy to serialize
    objects that use Enums as attributes.

    Example:
        >>> class Status(Enum):
        ...     OK = "ok"
        ...     FAIL = "fail"
        >>> json.dumps({'status': Status.OK}, cls=ObjectDecoder)
        '{"status": "ok"}'

    Methods:
        default(obj): returns the value of an Enum instance (a number for integer enums);
                      otherwise delegates to the default behavior.
    """

    def default(self, obj: Any) -> Any:
        # Convert Enum instances to their value: a number for integer enums, a string otherwise
        if isinstance(obj, Enum):
            return enum_value(obj)
        return super().default(obj)


def enum_value(member: Enum) -> Any:
    """Serialized value of an enum member: integer enums (IntEnum) stay numbers, the others are strings."""
    return int(member) if isinstance(member, int) else str(member.value)

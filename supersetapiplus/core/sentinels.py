from typing import Any


class MissingField:
    """
    Sentinel to mark a dataclass field that was not present
    in the incoming data.
    """
    def __repr__(self) -> str:
        return "<MissingField>"

    def __bool__(self) -> bool:
        # So that `if instance_of_MissingField:` is False
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MissingField)

    __hash__ = object.__hash__

    def to_json(self) -> Any:
        # If you have a custom JSON encoder, you can handle it here
        return None

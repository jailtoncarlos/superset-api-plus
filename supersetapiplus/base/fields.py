from typing import Any


class MissingField:
    """
    Sentinel to mark a dataclass field that was not present
    in the incoming data.
    """
    def __repr__(self):
        return "<MissingField>"

    def __bool__(self):
        # So that `if instance_of_MissingField:` is False
        return False

    def __eq__(self, other):
        return isinstance(other, MissingField)

    def to_json(self) -> Any:
        # If you have a custom JSON encoder, you can handle it here
        return None
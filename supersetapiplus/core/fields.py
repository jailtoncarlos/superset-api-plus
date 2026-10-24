import dataclasses
from typing import Any


def object_field(*, cls: type | None = None, default: Any = dataclasses.MISSING,
                 default_factory: Any = dataclasses.MISSING, init: bool = True, repr: bool = True,
                 hash: bool | None = None, compare: bool = True, metadata: dict[str, Any] | None = None,
                 kw_only: Any = dataclasses.MISSING, dict_left: bool = False, dict_right: bool = False) -> Any:
    """
    Create a custom dataclass field carrying the extra metadata used by supersetapiplus,
    such as custom serialization of dictionaries whose keys or values are `SerializableModel` instances.

    Wraps `dataclasses.field`, adding metadata used to automatically deserialize
    nested JSON structures.

    Parameters:
        cls (type, optional): `SerializableModel` subclass associated with the field. Used to
            instantiate nested objects during `from_json`.
        default: default value of the field. Cannot be combined with `default_factory`.
        default_factory: callable returning the field's default value. Cannot be combined with `default`.
        init (bool): whether the field is included in `__init__`. Defaults to True.
        repr (bool): whether the field is included in the `__repr__` output. Defaults to True.
        hash (bool | None): whether the field is used to compute the hash. If None, follows the `dataclass` default.
        compare (bool): whether the field is used in comparisons. Defaults to True.
        metadata (dict, optional): additional metadata, available to external logic.
        kw_only (bool): whether the field is keyword-only in `__init__`. Introduced in Python 3.10.
        dict_left (bool): if True, the field is a dictionary whose keys are `SerializableModel` instances.
        dict_right (bool): if True, the field is a dictionary whose values are `SerializableModel` instances.

    Returns:
        dataclasses.Field: field configured for use in a dataclass.

    Raises:
        ValueError: if both `default` and `default_factory` are given.
    """
    # Only one of default and default_factory may be given
    if default is not dataclasses.MISSING and default_factory is not dataclasses.MISSING:
        raise ValueError('cannot specify both default and default_factory')

    # Initialize the metadata, always including the library-specific keys
    metadata = metadata or {}
    metadata.update({
        "cls": cls,
        "dict_left": dict_left,
        "dict_right": dict_right,
    })

    # Return the field with all parameters configured
    return dataclasses.field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        kw_only=kw_only
    )


def json_field(**kwargs: Any) -> Any:
    """
    Create a dataclass field meant to hold JSON structures.

    The field is hidden from the representation (`repr=False`) and defaults
    to `None` when no `default` is given explicitly.

    Useful for attributes holding JSON strings or objects that are later
    serialized/deserialized.

    Args:
        **kwargs: additional arguments for `dataclasses.field`.

    Returns:
        dataclasses.Field: field configured for use in a dataclass.

    Example:
        class Example(SerializableModel):
            payload: dict = json_field()
    """
    if not kwargs.get('default'):
        # Default to None when not given explicitly
        kwargs['default'] = None

    # Create the field, hiding it from the instance's text representation
    return dataclasses.field(repr=False, **kwargs)


def default_string(**kwargs: Any) -> Any:
    """
    Create a dataclass field defaulting to the empty string ('') and hidden
    from the object's text representation (`repr=False`).

    Used for optional string attributes that should start empty, without
    having to write `default=''` on every field.

    Args:
        **kwargs: additional arguments for `dataclasses.field`.

    Returns:
        dataclasses.Field: field configured with `default=''` and `repr=False`.

    Example:
        class Example(SerializableModel):
            name: str = default_string()
    """
    if not kwargs.get('default'):
        # Default to the empty string when not given explicitly
        kwargs['default'] = ''

    # Create the field, hiding it from the instance's text representation
    return dataclasses.field(repr=False, **kwargs)


def default_bool(**kwargs: Any) -> Any:
    """
    Create a boolean dataclass field defaulting to `False` and hidden
    from the object's text representation (`repr=False`).

    Avoids repetition when declaring optional boolean fields that should
    start as `False`.

    Args:
        **kwargs: additional arguments for `dataclasses.field`.

    Returns:
        dataclasses.Field: boolean field configured with `default=False` and `repr=False`.

    Example:
        class Example(SerializableModel):
            active: bool = default_bool()
    """
    # Default to False when no default is given explicitly
    if not kwargs.get('default'):
        kwargs['default'] = False

    # Create the field with `repr=False` so it is not shown in __repr__
    return dataclasses.field(repr=False, **kwargs)

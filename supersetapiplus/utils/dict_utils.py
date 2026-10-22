from types import NoneType
from typing import Any


def detailed_dict_diff(d1, d2):
    """
    Compare two dictionaries and identify differences in keys and values.

    Returns:
        added (set): keys present in d1 but not in d2.
        removed (set): keys present in d2 but not in d1.
        modified (dict): keys present in both but with different values.
        same (set): keys present in both with equal values.
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o: (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = {o for o in intersect_keys if d1[o] == d2[o]}
    return added, removed, modified, same


def dicts_equal_and_all_values_none(dict1: dict[str, Any], dict2: dict[str, Any]) -> bool:
    """
    Check whether two dictionaries are equal and all their values are null
    (None or CustomNoneType instances).

    Args:
        dict1 (dict): first dictionary.
        dict2 (dict): second dictionary.

    Returns:
        bool: True if the dictionaries are equal and all values are null; False otherwise.
    """
    def all_values_null(d: dict) -> bool:
        # Check that every value is None or CustomNoneType
        return all(v is None or isinstance(v, NoneType) for v in d.values())

    return dict1 == dict2 and all_values_null(dict1) and all_values_null(dict2)


def dict_hash(my_dict):
    sorted_items = sorted(my_dict.items())
    hashed_items = [hash(item) for item in sorted_items]
    return hash(tuple(hashed_items))

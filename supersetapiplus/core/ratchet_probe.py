"""Temporary: checks that the CI rejects a function above complexity 10 and an import across the layers."""
from supersetapiplus.client import SupersetClient  # core must not import the client layer


def too_complex(value: int) -> int:
    if value == 1:
        return 1
    if value == 2:
        return 2
    if value == 3:
        return 3
    if value == 4:
        return 4
    if value == 5:
        return 5
    if value == 6:
        return 6
    if value == 7:
        return 7
    if value == 8:
        return 8
    if value == 9:
        return 9
    if value == 10:
        return 10
    return 0 if SupersetClient else -1

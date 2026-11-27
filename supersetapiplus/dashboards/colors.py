"""Categorical color schemes of the Superset frontend, for the color keys of a dashboard's ``json_metadata``.

On load, the dashboard frontend (``src/dashboard/actions/dashboardState.ts``, Superset 6.1.0) compares the stored
``color_scheme_domain`` with the colors of ``color_scheme`` in its categorical registry and, when they differ, asks to
store the fresh ones (``PUT /api/v1/dashboard/<id>/colors``), which a user who cannot edit the dashboard gets refused.
The schemes of that registry are shipped in ``profiles/`` of this package, written by
``bin/scripts/extract_color_schemes.py`` from the frontend source of each version. An instance may register more
(``EXTRA_CATEGORICAL_COLOR_SCHEMES``): their colors are not known here.
"""
import functools
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

#: Superset version whose schemes are used when none is given (the target of this release line).
DEFAULT_SCHEMES_VERSION = "6.1.0"


@dataclass(frozen=True)
class CategoricalColorScheme:
    """A categorical color scheme of the frontend registry: its id (the dashboard's ``color_scheme``), label and
    colors in order (the dashboard's ``color_scheme_domain``)."""
    id: str
    label: str
    colors: tuple[str, ...]


@functools.cache
def _registry(version: str) -> dict[str, Any]:
    path = resources.files(__package__).joinpath("profiles").joinpath(f"color_schemes_{version}.json")
    if not path.is_file():
        raise ValueError(f"no categorical color schemes for Superset {version}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def categorical_schemes(version: str = DEFAULT_SCHEMES_VERSION) -> dict[str, CategoricalColorScheme]:
    """The categorical schemes the frontend of `version` registers, by id, in registration order."""
    schemes: dict[str, dict[str, Any]] = _registry(version)["schemes"]
    return {scheme_id: CategoricalColorScheme(scheme_id, scheme["label"], tuple(scheme["colors"]))
            for scheme_id, scheme in schemes.items()}


def default_categorical_scheme(version: str = DEFAULT_SCHEMES_VERSION) -> str:
    """Id of the scheme the frontend of `version` uses by default (and in place of an unknown one)."""
    return str(_registry(version)["default"])


def categorical_scheme(scheme_id: str, version: str = DEFAULT_SCHEMES_VERSION) -> CategoricalColorScheme:
    """The categorical scheme `scheme_id` of the frontend of `version`; ValueError when it does not register it."""
    schemes = categorical_schemes(version)
    if scheme_id not in schemes:
        raise ValueError(f"unknown categorical color scheme {scheme_id!r}: Superset {version} registers "
                         f"{', '.join(schemes)}. For a scheme configured on the instance "
                         "(EXTRA_CATEGORICAL_COLOR_SCHEMES), pass its colors.")
    return schemes[scheme_id]

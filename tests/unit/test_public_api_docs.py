"""Every class and function exported in an `__all__` of the package has a docstring (issue: documentation)."""
import importlib
import inspect
import subprocess
import sys

import pytest

import supersetapiplus
import supersetapiplus.resources as resources
from supersetapiplus.core.api_model import ApiModel

PACKAGES = ["supersetapiplus", "supersetapiplus.core", "supersetapiplus.transport", "supersetapiplus.auth",
            "supersetapiplus.resources", "supersetapiplus.services", "supersetapiplus.datasets",
            "supersetapiplus.databases", "supersetapiplus.saved_queries", "supersetapiplus.assets"]


def exported():
    for package in PACKAGES:
        module = importlib.import_module(package)
        for name in module.__all__:
            obj = getattr(module, name)
            if inspect.isclass(obj) or inspect.isfunction(obj):
                yield f"{package}.{name}", obj


@pytest.mark.parametrize("name,obj", list(exported()), ids=[name for name, _ in exported()])
def test_exported_object_has_a_docstring(name, obj):
    # Its own docstring: not inherited, and not the signature @dataclass generates ("Name(field: type, ...)").
    doc = (obj.__dict__.get("__doc__") if inspect.isclass(obj) else obj.__doc__) or ""
    assert doc.strip() and not doc.startswith(f"{obj.__name__}("), f"{name} has no docstring"


def test_importing_the_package_does_not_load_superset_or_its_server_stack():
    """The library talks to Superset over HTTP and keeps checked excerpts of its sources instead of importing
    it (docs/studies/analysis/2026-10-24-superset-as-dependency.md): no server package is loaded."""
    code = ("import sys, supersetapiplus, supersetapiplus.client; "
            "print(sorted(m for m in sys.modules if m.split('.')[0] in "
            "('superset', 'flask', 'flask_appbuilder', 'sqlalchemy', 'marshmallow', 'pandas')))")
    loaded = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout

    assert loaded.strip() == "[]"


def test_resource_models_are_exported_by_the_package():
    """Applications import the resource models from `supersetapiplus`, as `Dataset` or `SavedQuery` (issue #13)."""
    models = {name for name in resources.__all__
              if inspect.isclass(getattr(resources, name)) and issubclass(getattr(resources, name), ApiModel)}

    assert models - set(supersetapiplus.__all__) == set()

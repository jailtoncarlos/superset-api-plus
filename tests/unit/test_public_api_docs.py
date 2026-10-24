"""Every class and function exported in an `__all__` of the package has a docstring (issue: documentation)."""
import importlib
import inspect

import pytest

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

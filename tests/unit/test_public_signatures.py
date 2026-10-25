"""No public function of the package takes a parameter annotated with a bare `Any`, unless the reason is declared.

Rule (fully typed public API): callers should not need to read the implementation to know what a parameter takes.
A parameter typed `Any` fails `test_no_public_parameter_is_a_bare_any` until it gets a real type (a model, a
protocol of `core.references`, `object` for any value inspected at run time, a union...) or is declared below with
the reason: a signature imposed by another library, or a free-form structure of Superset. Entries that no longer
match fail too. Compatibility modules of old paths (base, utils, security, layout.legacy) are left out.
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).parents[2] / "supersetapiplus"
LEGACY = ("base", "utils", "security", "legacy")

PYDANTIC = "signature of pydantic BaseModel.model_post_init (the validation context)"
REQUESTS = "keyword arguments forwarded to requests (timeout, params, files, headers...)"
DATACLASSES = "arguments forwarded to dataclasses.field, which types them as Any"

# Any method with this name and parameter, wherever it is declared.
BY_NAME = {"model_post_init(context)": PYDANTIC}

# "<module>.<qualname>(<parameter>)" -> reason.
ALLOWED = {
    "client.SupersetClient.get(kwargs)": REQUESTS,
    "client.SupersetClient.post(data)": "request body forwarded to requests (form data or bytes)",
    "client.SupersetClient.post(json)": "JSON request body forwarded to requests (any JSON-serializable value)",
    "client.SupersetClient.post(kwargs)": REQUESTS,
    "client.SupersetClient.put(data)": "request body forwarded to requests (form data or bytes)",
    "client.SupersetClient.put(kwargs)": REQUESTS,
    "client.SupersetClient.delete(kwargs)": REQUESTS,
    "resources.repository.HttpClient.get(kwargs)": REQUESTS,
    "resources.repository.HttpClient.post(kwargs)": REQUESTS,
    "resources.repository.HttpClient.put(kwargs)": REQUESTS,
    "resources.repository.HttpClient.delete(kwargs)": REQUESTS,
    "services.dashboard_charts._Client.get(kwargs)": REQUESTS,
    "services.dashboard_charts._Client.put(kwargs)": REQUESTS,
    "transport.http.RequestHandler.request_with_retry(kwargs)": REQUESTS,
    "core.encoding.ObjectDecoder.default(obj)": "signature of json.JSONEncoder.default (any object to encode)",
    "core.fields.object_field(default)": DATACLASSES,
    "core.fields.object_field(default_factory)": DATACLASSES,
    "core.fields.object_field(kw_only)": DATACLASSES,
    "core.fields.json_field(kwargs)": DATACLASSES,
    "core.fields.default_string(kwargs)": DATACLASSES,
    "core.fields.default_bool(kwargs)": DATACLASSES,
    "core.parse.ParseMixin.get_instance(kwargs)": "constructor arguments of the class resolved from the type name",
    "dashboards.native_filters.filter_config(control_values)":
        "the free-form controlValues of the native filter plugin (keys and values defined by each filter type)",
    "dashboards.metadata.Metadata.add_native_filter(options)":
        "keyword arguments of filter_config: its typed options and the free-form controlValues of the filter plugin",
}


def bare_any_parameters() -> set[str]:
    """`<module>.<qualname>(<parameter>)` of every public function parameter annotated with a bare `Any`."""
    found: set[str] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).with_suffix("")
        if any(part in LEGACY for part in relative.parts):
            continue
        module = ".".join(part for part in relative.parts if part != "__init__")
        found |= _in_module(ast.parse(path.read_text(encoding="utf-8")), module)
    return found


def _in_module(tree: ast.Module, module: str) -> set[str]:
    found: set[str] = set()

    def visit(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, [*scope, child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
                arguments = child.args
                parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                              *filter(None, [arguments.vararg, arguments.kwarg])]
                for parameter in parameters:
                    if parameter.annotation is not None and ast.unparse(parameter.annotation) == "Any":
                        found.add(f"{module}.{'.'.join([*scope, child.name])}({parameter.arg})")

    visit(tree, [])
    return found


def _declared(entry: str) -> bool:
    return entry in ALLOWED or entry.rsplit(".", 1)[-1] in BY_NAME


def test_no_public_parameter_is_a_bare_any():
    undeclared = sorted(entry for entry in bare_any_parameters() if not _declared(entry))

    assert undeclared == [], ("public parameters typed Any: give them a real type, or declare them in ALLOWED with "
                              f"the reason: {undeclared}")


def test_declared_exceptions_still_exist():
    stale = sorted(set(ALLOWED) - bare_any_parameters())

    assert stale == [], f"ALLOWED entries that are no longer bare Any parameters (remove them): {stale}"


def test_every_exception_has_a_reason():
    assert all(reason.strip() for reason in [*ALLOWED.values(), *BY_NAME.values()])

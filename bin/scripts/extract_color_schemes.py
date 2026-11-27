"""Extract the categorical color schemes the Superset frontend registers.

On load, the dashboard frontend (``src/dashboard/actions/dashboardState.ts``) compares the stored
``json_metadata.color_scheme_domain`` with the colors of ``color_scheme`` in its categorical registry
(``getColorSchemeDomain`` in ``src/utils/colorScheme.ts``) and asks to store them when they differ. The registry is
filled by ``src/setup/setupColors.ts`` with the schemes of
``packages/superset-ui-core/src/color/colorSchemes/categorical`` (plus the instance's
``EXTRA_CATEGORICAL_COLOR_SCHEMES``, not known here). This script downloads those files of the given version and
writes the schemes, in registration order, with the default scheme and their provenance: the package data read by
``supersetapiplus.dashboards.colors``.

Usage:
    python bin/scripts/extract_color_schemes.py 6.1.0 \
        > supersetapiplus/dashboards/profiles/color_schemes_6.1.0.json
"""
import json
import os
import re
import sys
import urllib.request

COMMIT_URL = "https://api.github.com/repos/apache/superset/commits/{ref}"
RAW_ROOT = "https://raw.githubusercontent.com/apache/superset/{version}/{path}"
SETUP_PATH = "superset-frontend/src/setup/setupColors.ts"
CATEGORICAL_DIR = "superset-frontend/packages/superset-ui-core/src/color/colorSchemes/categorical"

# registerColorSchemes(getCategoricalSchemeRegistry(), [...CategoricalX, ...], 'defaultKey')
REGISTRATION = re.compile(r"registerColorSchemes\(\s*getCategoricalSchemeRegistry\(\),\s*\[(.*?)\],\s*'(\w+)'",
                          re.DOTALL)
SPREAD = re.compile(r"\.\.\.(Categorical\w+)")
# export { default as CategoricalX } from './file';
EXPORT = re.compile(r"export \{ default as (Categorical\w+) \} from '\./(\w+)';")
SCHEME = re.compile(r"\{\s*id:\s*'([^']+)',\s*label:\s*'([^']*)',(.*?)colors:\s*\[(.*?)\],", re.DOTALL)
COLOR = re.compile(r"'(#[0-9A-Fa-f]{3,8})'")


def download(url: str | urllib.request.Request) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https URLs)
        return str(response.read().decode("utf-8"))


def commit_sha(ref: str) -> str:
    request = urllib.request.Request(COMMIT_URL.format(ref=ref), headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return str(json.loads(download(request))["sha"])


def registration(setup_source: str) -> tuple[list[str], str]:
    """The CategoricalX spreads registered in the categorical registry, in order, and the default scheme id."""
    match = REGISTRATION.search(setup_source)
    if not match:
        raise SystemExit("setupColors.ts: the categorical registration was not found (format changed?)")
    names = SPREAD.findall(match.group(1))
    if not names:
        raise SystemExit("setupColors.ts: no categorical scheme module is registered (format changed?)")
    return names, match.group(2)


def module_files(index_source: str) -> dict[str, str]:
    """CategoricalX -> file name (without .ts) of the categorical index."""
    files = dict(EXPORT.findall(index_source))
    if not files:
        raise SystemExit("categorical/index.ts: no export found (format changed?)")
    return files


def schemes_of(source: str, path: str) -> dict[str, dict]:
    """The schemes declared in one categorical module: id -> {label, colors, isDefault?}."""
    schemes = {}
    for scheme_id, label, between, body in SCHEME.findall(source):
        colors = COLOR.findall(re.sub(r"//[^\n]*", "", body))
        if not colors:
            raise SystemExit(f"{path}: scheme {scheme_id} has no color (format changed?)")
        scheme: dict = {"label": label, "colors": colors}
        if re.search(r"isDefault:\s*true", between):
            scheme["isDefault"] = True
        schemes[scheme_id] = scheme
    if not schemes:
        raise SystemExit(f"{path}: no scheme found (format changed?)")
    return schemes


def extract(version: str, fetch=lambda version, path: download(RAW_ROOT.format(version=version, path=path))) -> dict:
    names, default = registration(fetch(version, SETUP_PATH))
    files = module_files(fetch(version, f"{CATEGORICAL_DIR}/index.ts"))
    schemes: dict[str, dict] = {}
    paths = [SETUP_PATH, f"{CATEGORICAL_DIR}/index.ts"]
    for name in names:
        if name not in files:
            raise SystemExit(f"setupColors.ts registers {name}, which categorical/index.ts does not export")
        path = f"{CATEGORICAL_DIR}/{files[name]}.ts"
        paths.append(path)
        schemes.update(schemes_of(fetch(version, path), path))
    default = next((scheme_id for scheme_id, scheme in schemes.items() if scheme.get("isDefault")), default)
    if default not in schemes:
        raise SystemExit(f"the default scheme {default} is not among the registered schemes")
    return {"version": version, "default": default, "schemes": schemes, "provenance": {"paths": paths}}


def main(version: str) -> None:
    output = extract(version)
    output["provenance"].update({"repository": "apache/superset", "tag": version, "sha": commit_sha(version)})
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

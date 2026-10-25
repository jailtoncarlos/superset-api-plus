"""Report how newer Superset sources differ from the excerpts the library is checked against.

Runs the offline extractors (OpenAPI subset, enums, example layouts) on other Superset refs and compares
each result with the pinned fixture in tests/fixtures, ignoring provenance and version stamps. Run on the
pinned tag itself it proves the fixtures were not edited by hand; run on the newest release or on master
it lists what a version bump will have to decide (docs/superset-version-bump.md).

Usage:
    python bin/scripts/superset_drift.py [--pinned 6.1.0] [--report drift.md] [--out-dir DIR]
                                         [--fail-on REF] [REF ...]

REF is a tag, a branch or ``latest`` (the newest Superset release). ``--fail-on`` (repeatable) adds a ref
whose differences fail the run: exit status 1 when such a ref differs or fails to extract, 0 otherwise. The
other refs are reported only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "bin" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
LATEST_RELEASE_URL = "https://api.github.com/repos/apache/superset/releases/latest"

# Keys stamped with the ref or the commit: they always differ and say nothing about the contract.
IGNORED_KEYS = {"provenance", "superset_version", "version"}
# Fixture prefix → (extractor, depth of the reported paths). Below that depth a change is reported as a whole
# (a changed example layout is one line, not one per component).
EXCERPTS = {
    "superset_openapi": ("extract_openapi.py", 4),
    "superset_enums": ("extract_superset_enums.py", 3),
    "example_layouts": ("extract_example_layouts.py", 2),
}
MAX_LINES = 200


@dataclass
class Result:
    ref: str
    differences: dict[str, list[str]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def drifted(self) -> bool:
        return bool(self.errors) or any(self.differences.values())


def github_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:  # higher API rate limit on shared CI runners
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (fixed https URL)
        return dict(json.load(response))


def resolve(ref: str) -> str:
    return str(github_json(LATEST_RELEASE_URL)["tag_name"]) if ref == "latest" else ref


def pinned_version() -> str:
    """The target version, from the name of the enums excerpt (one per supported version)."""
    versions = sorted(p.name[len("superset_enums_"):-len(".json")] for p in FIXTURES.glob("superset_enums_*.json"))
    if len(versions) != 1:
        raise SystemExit(f"Expected one enums excerpt in tests/fixtures, found {versions}; pass --pinned.")
    return versions[0]


def _scalar_list(value: object) -> bool:
    return isinstance(value, list) and all(not isinstance(item, (dict, list)) for item in value)


def _show(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 80 else text[:77] + "..."


def _diff_lists(path: str, old: list, new: list) -> list[str]:
    old_items = {json.dumps(i, sort_keys=True) for i in old}
    new_items = {json.dumps(i, sort_keys=True) for i in new}
    return ([f"+ {path}[] {item}" for item in sorted(new_items - old_items)]
            + [f"- {path}[] {item}" for item in sorted(old_items - new_items)])


def diff(old: object, new: object, depth: int, path: str = "") -> list[str]:
    """Lines `+ path value`, `- path value` and `~ path old → new` describing how `new` differs from `old`."""
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict) and depth > 0:
        lines: list[str] = []
        for key in sorted(old.keys() | new.keys()):
            child = f"{path}.{key}" if path else str(key)
            if key not in new:
                lines.append(f"- {child} {_show(old[key])}")
            elif key not in old:
                lines.append(f"+ {child} {_show(new[key])}")
            else:
                lines.extend(diff(old[key], new[key], depth - 1, child))
        return lines
    if _scalar_list(old) and _scalar_list(new):
        return _diff_lists(path, old, new)  # type: ignore[arg-type]
    return [f"~ {path or '(root)'} {_show(old)} → {_show(new)}"]


def compare(pinned: dict, current: dict, depth: int) -> list[str]:
    strip = lambda data: {k: v for k, v in data.items() if k not in IGNORED_KEYS}  # noqa: E731
    return diff(strip(pinned), strip(current), depth)


def extract(script: str, ref: str, out_dir: Path | None) -> dict:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), ref], capture_output=True, text=True,
                          check=False, timeout=900)
    if proc.returncode != 0:
        last = (proc.stderr or proc.stdout).strip().splitlines()[-1:]
        raise RuntimeError(last[0] if last else f"exit status {proc.returncode}")
    if out_dir:
        (out_dir / f"{script.removeprefix('extract_').removesuffix('.py')}_{ref}.json").write_text(
            proc.stdout, encoding="utf-8")
    return dict(json.loads(proc.stdout))


def check(ref: str, pinned: str, out_dir: Path | None) -> Result:
    result = Result(ref)
    for prefix, (script, depth) in EXCERPTS.items():
        fixture = json.loads((FIXTURES / f"{prefix}_{pinned}.json").read_text(encoding="utf-8"))
        try:
            result.differences[prefix] = compare(fixture, extract(script, ref, out_dir), depth)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            result.errors[prefix] = str(error)
    return result


def report(results: list[Result], pinned: str, resolved: dict[str, str]) -> str:
    aliases = {ref: f" ({name})" for name, ref in resolved.items() if name != ref}
    lines = [f"# Superset drift against the pinned {pinned} excerpts", ""]
    for result in results:
        status = "differs" if result.drifted else "no difference"
        lines += [f"## {result.ref}{aliases.get(result.ref, '')}: {status}", ""]
        for prefix, error in result.errors.items():
            lines += [f"- `{prefix}`: **extraction failed**: {error}"]
        for prefix, changes in result.differences.items():
            lines += [f"- `{prefix}`: {len(changes)} difference(s)"]
            if changes:
                shown = changes[:MAX_LINES]
                more = [f"... {len(changes) - MAX_LINES} more"] if len(changes) > MAX_LINES else []
                lines += ["", "```diff", *shown, *more, "```", ""]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("refs", nargs="*")
    parser.add_argument("--pinned")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--fail-on", action="append", default=[], metavar="REF")
    args = parser.parse_args(argv)
    if not args.refs and not args.fail_on:
        parser.error("give at least one REF")
    pinned = args.pinned or pinned_version()
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    resolved = {ref: resolve(ref) for ref in dict.fromkeys(args.refs + args.fail_on)}
    # `latest` may be the pinned tag or another listed ref: each Superset ref is extracted once.
    results = [check(ref, pinned, args.out_dir) for ref in dict.fromkeys(resolved.values())]
    text = report(results, pinned, resolved)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text)
    failing = {resolved[ref] for ref in args.fail_on}
    return 1 if any(r.drifted for r in results if r.ref in failing) else 0


if __name__ == "__main__":
    sys.exit(main())

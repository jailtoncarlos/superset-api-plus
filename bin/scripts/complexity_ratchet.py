"""Block new or increased cyclomatic complexity > 10 (ruff C901) without penalizing legacy code.

Pre-commit hook. For each file, compares the functions above 10 in the base with the
current ones (by qualname, `Class.method`) and rejects new ones, those that crossed the
limit, and legacy ones already above 10 whose complexity increased. An edited complex
legacy function that does not increase its complexity passes (5 legacy functions in this
library as of 2026-10-22).

Base: on a local commit, `HEAD` (pre-commit stashes unstaged changes, so the tree = the
staged content); in CI (`--from-ref/--to-ref`), the merge-base of both refs. A renamed
file (`git mv`) is compared against its old path.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

LIMIT = 10


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=False)


def base_ref() -> str:
    """Merge-base of from/to in CI mode; otherwise HEAD."""
    source, target = os.environ.get('PRE_COMMIT_FROM_REF'), os.environ.get('PRE_COMMIT_TO_REF')
    if not (source and target):
        return 'HEAD'
    proc = git('merge-base', source, target)
    return proc.stdout.strip() if proc.returncode == 0 else source


def renamed(base: str) -> dict[str, str]:
    """Map new_path -> old_path of the files renamed since the base."""
    output = git('diff', '-M', '--name-status', base).stdout
    mapping: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split('\t')
        if parts[0].startswith('R') and len(parts) == 3:
            mapping[parts[2]] = parts[1]
    return mapping


def qualnames(source: str) -> dict[int, str]:
    """Line of the `def` -> qualname (`Class.method`, `function.inner`)."""
    names: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f'{prefix}{child.name}'
                if not isinstance(child, ast.ClassDef):
                    names[child.lineno] = name
                visit(child, f'{name}.')
            else:
                visit(child, prefix)

    try:
        visit(ast.parse(source), '')
    except SyntaxError:
        return {}
    return names


def complex_functions(source: str, path: str) -> dict[str, list[tuple[int, str]]]:
    """qualname -> (complexity, ruff message) of each function above the limit, in file order."""
    if not source:
        return {}
    proc = subprocess.run(
        [
            'ruff',
            'check',
            '--select',
            'C901',
            '--config',
            f'lint.mccabe.max-complexity={LIMIT}',
            '--output-format',
            'json',
            '--stdin-filename',
            path,
            '-',
        ],
        input=source,
        capture_output=True,
        text=True,
        check=False,
    )
    names = qualnames(source)
    findings: dict[str, list[tuple[int, str]]] = {}
    for item in json.loads(proc.stdout or '[]'):
        line, message = item['location']['row'], item['message']
        value = int(re.search(r'\((\d+) > ', message).group(1))
        findings.setdefault(names.get(line, f'<line {line}>'), []).append((value, f'{path}:{line}: {message}'))
    return findings


def rejected_in_file(path: str, base: str, old_path: str) -> list[str]:
    """Messages of the functions above the limit that are new or more complex than in the base.

    Same-named functions (`clean` in two classes have distinct qualnames; getter/setter do
    not) are paired by order in the file; any extra current occurrence counts as new.
    """
    now = complex_functions(Path(path).read_text(), path)
    before = complex_functions(git('show', f'{base}:{old_path}').stdout, path)
    rejected: list[str] = []
    for name, occurrences in now.items():
        base_values = [value for value, _ in before.get(name, [])]
        for i, (value, msg) in enumerate(occurrences):
            previous = base_values[i] if i < len(base_values) else None
            if previous is None:
                rejected.append(msg)
            elif value > previous:
                rejected.append(f'{msg} [was {previous}]')
    return rejected


def main(files: list[str]) -> int:
    base = base_ref()
    mapping = renamed(base)
    rejected = [
        msg
        for path in files
        if Path(path).is_file()
        for msg in rejected_in_file(path, base, mapping.get(path, path))
    ]
    if not rejected:
        return 0
    header = [
        f'New or increased cyclomatic complexity > {LIMIT} (ruff C901).',
        f'Refactor to <= {LIMIT} (extract helpers, simplify branches), or at least do not increase the legacy one:',
    ]
    sys.stderr.write('\n'.join([*header, *(f'  - {msg}' for msg in rejected)]) + '\n')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

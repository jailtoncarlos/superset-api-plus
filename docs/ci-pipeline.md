# CI pipeline

The GitHub Actions workflows in `.github/workflows/`: what each one runs, when, and how to reproduce a job
locally. For the test suites themselves see [testing.md](testing.md). CI/CD changes require explicit
authorization from the maintainer (AGENTS.md).

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| Python package | `python-package.yaml` | pull requests; pushes to `main` | lint, tests, lowest versions, integration, example dashboards |
| Superset drift | `superset-drift.yaml` | Mondays 06:17 UTC; manual | newest Superset release and master vs. the pinned excerpts |
| Build & Publish Python Package | `publishing.yaml` | a GitHub release is published | build and upload to PyPI |

## Python package (`python-package.yaml`)

Branches are tested through their pull request (there is no push trigger on other branches, which ran each PR
commit twice). On a pull request a new commit cancels the run of the previous one; runs on `main` always
finish (`concurrency`, `cancel-in-progress` only for `pull_request`).

All jobs run on `ubuntu-latest` and install uv 0.12.2 with `astral-sh/setup-uv`. The environment comes from
`uv.lock` (`uv sync --locked`, which fails when the lock is out of date with `pyproject.toml`), except in the
`lowest` job.

| Job | When | Python | What it runs |
|---|---|---|---|
| `lint` | pull requests only | 3.12 | pre-commit on the PR diff |
| `test` | always | 3.10, 3.11, 3.12, 3.13, 3.14 | the whole `tests/` tree with coverage |
| `lowest` | always | 3.10, 3.14 | `tests/unit` with the lowest direct dependency versions |
| `integration` | always | 3.12 | `tests/integration` against the compose stack |
| `examples` | always | 3.12 | `tests/integration/test_examples` against the stack with the examples loaded |

The jobs are independent and run in parallel; `test` and `lowest` use `fail-fast: false`, so one Python
version failing does not cancel the others.

### `lint`

Checks out the full history (`fetch-depth: 0`: the complexity ratchet compares against the merge-base of the
target branch), runs `uv sync --locked --all-extras` and then the same hooks as the local pre-commit, applied
only to the files the PR changes:

```bash
uv run --locked --all-extras pre-commit run --show-diff-on-failure --from-ref origin/main --to-ref HEAD
```

The hooks (`.pre-commit-config.yaml`): end-of-file fixer, JSON/YAML/merge-conflict/large-file checks, LF line
endings, codespell, ruff, the complexity ratchet (`bin/scripts/complexity_ratchet.py`, ruff C901 limit 10),
`mypy --strict`, import layers (`lint-imports`), Superset conformance
(`tests/unit/test_openapi_conformance.py`) and model attributes (enum, `str` field, UI default and extractor
tests). The job is skipped on pushes to `main`: what reaches `main` went through it on the PR.

### `test`

```bash
uv sync --locked --extra test --extra graph
uv run --locked --extra test --extra graph pytest --cov=supersetapiplus tests
```

The whole `tests/` tree runs, so no test directory can be left out of CI unnoticed; the integration tests skip
themselves without a Superset (see [testing.md](testing.md#integration-tests)).

### `lowest`

The runtime dependency floors in `pyproject.toml` stay at or below the constraints of the Airflow version used
by the integration that embeds the library, so the unit suite must pass with the lowest direct versions. They
are installed with `uv pip`, which leaves `uv.lock` untouched:

```bash
uv venv
uv pip install --resolution lowest-direct ".[test]"
.venv/bin/python -m pytest tests/unit
```

### `integration`

Starts the compose stack configured by `.env.example` (Superset 6.1.0 and Postgres 16 on
`127.0.0.1:8089`), waits up to 10 minutes for `/health`, and runs the integration tests against it:

```bash
cp .env.example .env
docker compose -p superset-api-plus up -d --build
timeout 600 bash -c 'until curl -sf http://127.0.0.1:8089/health >/dev/null; do sleep 5; done'
SUPERSET_INTEGRATION=1 uv run --locked --extra test pytest -v tests/integration
docker compose -p superset-api-plus down -v
```

On failure the job prints the last 200 lines of the Superset logs; the stack is always stopped and its volumes
removed. Timeout: 30 minutes.

### `examples`

The same stack loading the example dashboards shipped with Superset (`SUPERSET_LOAD_EXAMPLES=1`, a few
minutes; the health wait goes up to 20 minutes):

```bash
sed 's/^SUPERSET_LOAD_EXAMPLES=.*/SUPERSET_LOAD_EXAMPLES=1/' .env.example > .env
docker compose -p superset-api-plus up -d --build
timeout 1200 bash -c 'until curl -sf http://127.0.0.1:8089/health >/dev/null; do sleep 10; done'
SUPERSET_INTEGRATION=1 SUPERSET_EXAMPLES_REQUIRED=1 \
  uv run --locked --extra test pytest -v tests/integration/test_examples -W always::UserWarning
docker compose -p superset-api-plus down -v
```

`SUPERSET_EXAMPLES_REQUIRED=1` makes a stack that did not load the examples fail instead of skipping.
`-W always::UserWarning` keeps every `NotCoveredWarning` (charts of a viz_type the library does not model) and
`KnownDivergenceWarning` (charts with an open issue, `known_divergences.py`) in the warnings summary, which is
where to read what the library does not cover yet. Logs on failure, stack always stopped, timeout 30 minutes.

## Superset drift (`superset-drift.yaml`)

Runs `bin/scripts/superset_drift.py`: the offline extractors (OpenAPI subset, enums, example layouts) on the
newest Superset release and on the extra refs, compared with the pinned excerpts in `tests/fixtures/`. It fails
when the newest release differs from them (a new release to support, or a fixture edited by hand); the extra
refs (`master` by default) are reported only.

- Schedule: Mondays at 06:17 UTC. By hand: *Actions → Superset drift → Run workflow*, with `refs` set to the
  tags or branches to report (space-separated).
- Python 3.12 with `pyyaml` only (the package is not installed). `GITHUB_TOKEN` authenticates the GitHub API
  calls of the extractors (higher rate limit). Permissions: `contents: read`.
- The report (`drift.md`) is the job summary; `drift.md` and `drift/` are uploaded as the `superset-drift`
  artifact.

Locally (`GITHUB_TOKEN` is optional):

```bash
python bin/scripts/superset_drift.py --report drift.md --out-dir drift --fail-on latest master
```

A failing run is the start of a version bump: [superset-version-bump.md](superset-version-bump.md), step 0.

## Build & Publish Python Package (`publishing.yaml`)

Runs when a GitHub release is **published** (a draft release does not trigger it): `python -m build` and the
upload to PyPI with `pypa/gh-action-pypi-publish`, authenticated by the repository secret `PYPI_API_TOKEN`.
Publishing the release is therefore what puts a version on PyPI. To tag a version without publishing it, create
the release as a draft from the tag of the release merge commit:

```bash
gh release create vX.Y.Z --draft --verify-tag --title vX.Y.Z --notes-file notes.md
```

and publish the draft when the version should reach PyPI.

## Reading a run

- A PR is ready when every job of `python-package.yaml` is green; on `main` `lint` shows as skipped.
- `gh run list --workflow python-package.yaml --branch <branch>` lists the runs of a branch;
  `gh run view <run id> --log-failed` prints the log of the failing steps.
- In the `examples` job, the warnings summary at the end of the pytest output lists the
  `NotCoveredWarning`/`KnownDivergenceWarning` entries.

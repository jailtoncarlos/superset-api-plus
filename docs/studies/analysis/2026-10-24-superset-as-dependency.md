---
title: "Import Superset's classes or keep checked copies?"
type: analysis
audience: human+ai-agent
updated: 2026-10-24
cutoff: 2026-10-24
confidence: 0.9
tldr: |
  A blind review (an independent agent that did not read this repository's documentation or the
  current decision) recommends keeping the library's own enums and models, generated from and checked
  against the pinned Superset sources, and never depending on apache-superset at runtime.
  apache-superset 6.1.0 cannot be installed next to Airflow 3 (SQLAlchemy <2 vs >=2.0.50), does not
  support Python 3.13/3.14, starts the Flask app on any import, and covers about a quarter of the
  vocabulary the library needs (most of it lives in the TypeScript frontend).
tags: [analysis, architecture, dependencies, superset, decision]
related:
  - docs/studies/research/2026-10-24-superset-client-landscape.md
  - docs/studies/analysis/2026-10-24-landscape-impact.md
  - bin/scripts/extract_superset_enums.py
---

# Import Superset's classes or keep checked copies?

## Question

Superset is written in Python. Should the library import Superset's own classes (enums, schemas,
constants, the MCP service's pydantic models) instead of keeping copies whose coherence with Superset is
enforced by generated fixtures and pre-commit/CI conformance checks?

## Method

The question was given to an independent agent **blind**: it was told the usage constraints (remote
REST client embedded in Airflow tasks, Python 3.10–3.14, one pinned Superset version at a time, public
PyPI package) but was forbidden to read `AGENTS.md`, `README.md`, `CHANGELOG` and `docs/`, which state
the current decision. It could read the library code, tests and extraction scripts, PyPI metadata and the
Superset 6.1.0 sources. Its two decisive pieces of evidence were re-checked afterwards (marked ✔).

## Evidence

| Evidence | Source |
|---|---|
| ✔ `apache-superset` 6.1.0 requires `sqlalchemy<2,>=1.4`; `apache-airflow-core` 3.3.2 requires `sqlalchemy[asyncio]>=2.0.50`: they cannot share an environment | PyPI JSON metadata of both releases |
| `apache-superset` also pins `pandas<2.2`, `numpy<2.3`, `pyarrow<19`, `marshmallow<4`, `celery<6`, `redis<6`, `selenium<5` among about 60 runtime dependencies; the wheel is about 104 MB. The library needs 6 small packages | PyPI; `pyproject.toml` |
| `pandas<2.2` resolves to 2.1.4, with wheels up to CPython 3.12 only; Superset 6.1.0 declares 3.10–3.12. The library is tested on 3.10–3.14 | PyPI |
| ✔ `superset/__init__.py` imports `superset.app.create_app` and `superset.extensions`, so even `import superset.constants` loads the Flask app stack | Superset 6.1.0 `superset/__init__.py:19-31` |
| `superset/utils/core.py` and `superset/charts/schemas.py` import `flask.current_app`, SQLAlchemy and DB engine specs; `charts/schemas.py` reads `current_app.config` | Superset 6.1.0 |
| The supported integration package `apache-superset-core` 0.1.0 exposes no viz types, operators, time grains or aggregates and also pins `sqlalchemy<2.0` | PyPI |
| `superset/mcp_service` exists at 6.1.0 but imports `superset.constants` and DAOs, and models simplified LLM-oriented configs, not the REST `params`/`query_context` contract | Superset 6.1.0 `mcp_service/chart/schemas.py:43-44` |
| Most of the vocabulary is TypeScript-only: the extractor reads 8 backend enums against 18 frontend enums, union types, AGGREGATES, D3 formats and about 10 control panel choice sets; `build_query.py` ports frontend code | `bin/scripts/extract_superset_enums.py`; `supersetapiplus/charts/build_query.py` |
| Preset's own `preset-cli` does not depend on `apache-superset` | PyPI metadata of `preset-cli` 0.3.13 |
| Hand-written value sets drift even inside Superset: its 6.1.0 MCP service accepts aggregates the 6.1.0 backend cannot execute | [follow-up audit](./2026-10-24-layout-errors-enums-audit.md), section 3 |

## Options compared

| Criterion | A: import Superset | B: own copies + checks | Recommended: B with generation and drift detection |
|---|---|---|---|
| Installs next to Airflow 3 | no | yes | yes |
| Footprint | ~104 MB, ~60 deps | small | small (generation is dev-time) |
| Import side effects | Flask app at import | none | none |
| Python 3.13/3.14 | breaks | yes | yes |
| Coverage incl. TypeScript-only values and buildQuery | ~25% | full | full |
| API stability | internal modules, no promise | controlled | controlled; drift fails tests |
| Several Superset versions | one installed per environment | fixtures per version | fixtures per version |
| Drift risk | none for the covered part | real, mitigated by tests | low, plus early warning |

## Decision

Keep option B, as already practiced: Superset sources (Python and TypeScript, at the pinned tag) are
**inputs** to `bin/scripts/extract_*.py`, which produce versioned fixtures; conformance tests compare the
library's enums and models with them. Superset is never a runtime or test dependency.

The recommendation flips if Superset publishes a lightweight, dependency-free package with the REST
vocabulary and declares it stable, if the library becomes a Superset extension running in-process, or if
Superset publishes a complete OpenAPI with enums and a form-data JSON schema from which a client could be
generated.

## Hardening practices (become tasks)

1. Record the tag, commit SHA and source paths in every generated fixture, so a manual edit is detectable.
2. Optionally generate values-only enums into a generated module re-exported by the hand-written ones;
   keep semantic code (buildQuery, defaults, layout) hand-written and checked against captures.
3. Make the TypeScript extraction fail loudly when an expected symbol is missing, and unit-test the
   extractors.
4. Add a test that fails when a fixture key is no longer referenced by any enum.
5. Scheduled drift job against the newest Superset tag (and optionally master) that reports the diff
   before a version bump. It is a CI change and needs the maintainer's authorization.
6. A CI check that imports `supersetapiplus` with the lowest dependency versions and without Flask or
   SQLAlchemy installed, proving Superset never leaks into the runtime path.

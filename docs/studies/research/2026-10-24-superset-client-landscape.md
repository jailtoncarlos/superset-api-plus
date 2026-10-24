---
title: "Landscape of Apache Superset client libraries, CLIs and MCP servers"
type: research
audience: human+ai-agent
updated: 2026-10-24
cutoff: 2026-10-24
confidence: 0.8
tldr: |
  Nine projects overlap with superset-api-plus. None is a Python library with typed
  per-viz_type chart models, lossless round trip and tests against a real Superset.
  The closest in intent is Superset's own built-in MCP service (pydantic chart configs,
  layout validator, native filter tools), which runs inside the Superset process and
  is not usable as a remote client. Preset's CLIs manage assets as YAML; community MCP
  servers and superset-ai pass raw or loosely modeled payloads and are tested with mocks.
tags: [research, superset, ecosystem, clients, mcp, landscape]
related:
  - docs/studies/analysis/2026-10-24-landscape-impact.md
---

# Landscape of Apache Superset client libraries, CLIs and MCP servers

## TL;DR

- The library was started in January 2025 as a fork of `opus-42/superset-api-client`. Since then the
  ecosystem grew in three directions: **assets as code** (Preset `preset-cli`, `sup`), **MCP servers for
  LLM agents** (Superset's built-in `mcp_service` plus community servers) and **natural-language
  dashboard builders** (`superset-ai`).
- **No project found covers the same niche**: an importable Python client whose chart models are typed per
  `viz_type`, whose request fields and values are traced to a pinned Superset version, that derives
  `query_context` the way the frontend does, round-trips objects without loss and is tested against a
  real Superset.
- **Apache Superset's `mcp_service`** is the most relevant reference. It models charts with pydantic
  configs (7 chart types in 6.1.0, about 20 on master), validates dashboard layouts with the frontend's
  parent/child depth rules and manages native filters. It runs in-process (DAOs, commands), so it is a
  source of rules to cross-check, not a dependency.
- Every other project inspected tests with HTTP mocks only. Several carry defects that a test against a
  real server would catch: legacy `viz_type`s, a generic `query_context` wrong for most plugins,
  broken token refresh, lossy updates.

## Method

1. Search on GitHub (`gh search repos`) and PyPI for Superset clients, SDKs, "dashboard as code" tools and
   MCP servers, plus web search for 2025–2026 announcements.
2. Shallow clone of each candidate at the commit listed below; read-only code inspection (nothing from the
   clones was installed or executed). Superset was cloned with a sparse checkout of
   `superset/mcp_service`.
3. Each project was compared with this library on: scope, chart modeling, source of allowed values,
   `form_data`/`query_context` building, dashboard layout, native filters, round trip, authentication,
   HTTP robustness, tests, targeted Superset version and license.
4. Findings that point to defects in this library were re-checked in our code before being recorded in
   the [analysis](../analysis/2026-10-24-landscape-impact.md).

## Inventory

| Project | Kind | Language | License | Inspected commit (date) | Activity | Superset target |
|---|---|---|---|---|---|---|
| [apache/superset `mcp_service`](https://github.com/apache/superset/tree/master/superset/mcp_service) | MCP server built into Superset | Python | Apache-2.0 | `1721cbe` (2026-10-24) | very active | master (in-process) |
| [preset-io/backend-sdk](https://github.com/preset-io/backend-sdk) (`preset-cli`, `superset-cli`) | CLI + helper client | Python | proprietary ("All rights reserved") | `0921f1b` (2026-10-12) | active | runtime detection, back to 1.x |
| [preset-io/superset-sup](https://github.com/preset-io/superset-sup) (`sup`) | git-like CLI | Python | BSL 1.1 | `a0f5f79` (2026-06-23) | active | Preset workspaces / Superset |
| [bintocher/mcp-superset](https://github.com/bintocher/mcp-superset) | MCP server (137 tools) | Python | MIT | `4e0a856` (2026-09-19) | active | 5.x/6.x |
| [aptro/superset-mcp](https://github.com/aptro/superset-mcp) | MCP server | Python | MIT | `b3dd425` (2025-07-28) | low | unspecified |
| [Winding2020/superset-mcp](https://github.com/Winding2020/superset-mcp) | MCP server | TypeScript | MIT | `ff8e0eb` (2026-10-01) | active | unspecified |
| [braislchao/superset-ai](https://github.com/braislchao/superset-ai) | NL agent + async client | Python | MIT | `3a3090f` (2026-03-02) | single release | 3.1.0 stack, claims 6.x |
| [opus-42/superset-api-client](https://github.com/opus-42/superset-api-client) | client library | Python | Apache-2.0 | `900ca1b` (2023-06-12) | dormant | 2.0 |
| [ishahroz/superset-python-client](https://github.com/ishahroz/superset-python-client) | client library (fork of opus-42) | Python | Apache-2.0 | `6546538` (2024-12-21) | dormant | 4.0.2 |

Not inspected: forks without changes, Java/React clients (`SupersetApiClient-java`, Kiota-generated
clients), and "dashboard as code" lab repositories without a reusable library.

## Projects

### Apache Superset `mcp_service` (built-in MCP server)

- **Scope.** A FastMCP server on a Flask app singleton inside Superset
  (`superset/mcp_service/ARCHITECTURE.md:28-100`). Tools call DAOs and commands directly:
  `CreateChartCommand` (`chart/tool/generate_chart.py:337,496`), `UpdateDashboardCommand`
  (`dashboard/tool/add_chart_to_existing_dashboard.py:234,359`), `UpdateDashboardNativeFiltersCommand`
  (`dashboard/tool/manage_native_filters.py:809-838`). It cannot be imported outside Superset.
- **Chart modeling.** Pydantic configs keyed by an abstract `chart_type` (`pie`, `table`, `xy`,
  `pivot_table`, `mixed_timeseries`, `big_number`, `handlebars` in 6.1.0; plus `box_plot`, `bubble_v2`,
  `bullet`, `gantt`, `gauge`, `histogram`, `sunburst`, `treemap_v2`, `waterfall`, `world_map`,
  `country_map`, `deck_scatter`, `interactive_pivot` on master), mapped to native `form_data` by
  `map_*_config` functions (`chart/chart_utils.py`). Unknown input keys are rejected with suggestions
  (`UnknownFieldCheckMixin`); an omitted field differs from an explicit null (`OmittedMeansUnchanged`,
  `utils/schema_utils.py:56-78`). Allowed values are inline `Literal`s, with no source citation or
  conformance test.
- **Query context.** Charts are saved with `params` only; `update_chart` clears `query_context`
  (`chart/tool/update_chart.py:357,456`). Queries are rebuilt server-side by a backend port of buildQuery
  (`superset.common.form_data_query_context`, outside the sparse checkout). A two-tier check validates
  column/metric references, then runs the query with `row_limit=2` (`chart/compile.py:17-30`).
- **Dashboard layout.** Fixed ROW > COLUMN > CHART placement (`dashboard/tool/generate_dashboard.py:60-125`),
  plus a full validator: parent/child depth table ported from the frontend's `isValidChild.ts`, cycle
  detection, meta checks (`dashboard/layout_validation.py:34-90,203-323`), grid limits
  (`dashboard/constants.py:27-30`: row height 5–100 units, width 1–12).
- **Native filters.** Select, range, time, time grain and divider; scope "only these charts" becomes
  `{"rootPath": ["ROOT_ID"], "excluded": [...]}` (`manage_native_filters.py:264-283`); default values are
  turned into a data mask mirroring `getSelectExtraFormData` (`:120-170`); a time filter has
  `targets: [{}]` (`:371-377`); a range filter requires a numeric column (`:449`).
- **Tests.** Mock-based unit tests under `tests/unit_tests/mcp_service/` (per its `CLAUDE.md:503-563`).
- **Value sets that differ from 6.1.0.** Master adds a `"Metric"` pivot aggregate and `STDDEV_SAMP`,
  `VAR_SAMP`, `MEDIAN`, `PERCENTILE` aggregates (`chart/chart_utils.py:1294-1311`); these are post-6.1.0.

### Preset `backend-sdk` (`preset-cli`, `superset-cli`)

- **Scope.** Click CLI over a generic `SupersetClient` (`src/preset_cli/api/clients/superset.py:242`):
  `get/create/update/delete_resource` with `**kwargs` in and dicts out; `TypedDict` hints only.
- **Features.** Native YAML asset sync with Jinja templating and `.overrides` files
  (`cli/superset/sync/native/command.py`); import in dependency order with checkpoint and
  continue-on-error (`:440-616`); safe ZIP extraction (`:205-227`); Jinja escaping on export
  (`export.py:509-515`); export in batches of 50 IDs with ZIP merge (`superset.py:816-838`); dbt sync of
  datasets, metrics and exposures with a reload/merge/keep strategy (`sync/dbt/datasets.py:171-240`);
  RBAC, RLS and ownership import/export (`superset.py:953-1425`).
- **Auth/HTTP.** Re-login on any 401 (no refresh token) (`auth/main.py:46-83`); CSRF fetched after login,
  with HTML scraping fallback (`auth/superset.py:131-189`); urllib3 `Retry(total=3)` on all methods,
  mounted for `https://` only (`auth/main.py:22-29`); no timeouts found; the request resent after
  re-authentication uses `verify=False` (`auth/main.py:83`).
- **Charts/dashboards.** Opaque `params`; layout and native filters pass through YAML untouched.
- **Tests.** Mocked (`requests_mock`, `pytest-mock`); no live Superset.

### Preset `superset-sup` (`sup`)

- Typer/Rich CLI with a git-like pull/push interface, multi-target sync with per-target Jinja context
  (`sup/config/sync.py:80-131`), table/JSON/YAML/CSV/porcelain output (`sup/output/formatters.py:38-63`).
- Vendors a diverged fork of `preset_cli` inside its tree and wraps its client
  (`sup/clients/superset.py:12,19`); requires a Preset workspace to resolve the host (`:30-66`).
- Charts are listed, shown and pulled; data is fetched by posting the stored `query_context`
  (`sup/clients/superset.py:478-520`).

### `bintocher/mcp-superset`

- Async httpx client with JWT (with refresh), CSRF and static SSO cookie auth (`src/mcp_superset/auth.py`);
  tools take raw JSON strings.
- Retries once when a 400 body mentions an expired CSRF token, refetching the token
  (`client.py:160-172,322-337`); flattens `errors[].extra.issue_codes[].message` into readable text
  (`client.py:75-110`).
- Hand-written viz_type allow/deny sets that map removed types to replacements (`tools/charts.py:36-57`);
  rejects moment.js date formats (`:226-237`); rejects KPI tiles below height 16
  (`tools/dashboards.py:10,203-240`); warns when a filter column is missing from a chart's dataset
  (`:120-138`).
- Risky behaviors: adding a native filter sets `always_filter_main_dttm=True` on datasets and rewrites
  chart `params` without updating `query_context` (`tools/dashboards.py:17-53,174-180,813-826`);
  `tabsInScope: []` hard-coded and `chartsInScope` taken as a snapshot (`:793-795,1034-1036`); chart copy
  reuses the source `query_context` with the old `slice_id` (`tools/charts.py:727-730`).
- Tests: 32 unit tests mocked with respx.

### `aptro/superset-mcp`

- A single 1844-line `main.py` with 64 tools; raw dicts, no tests.
- Token refresh posts the access token to `/security/refresh` and never stores the refresh token, so it
  always fails (`main.py:387,482`); `json_metadata` is sent as a dict instead of a string (`:564-565`);
  the JWT is written in plaintext to `.superset_token` (`:62,90-96`).

### `Winding2020/superset-mcp`

- TypeScript with Axios clients; zod "params schemas" for 24 viz_types served by a `get_chart_params`
  tool (`src/schema/index.ts:68-78`). The schemas are hand-written, cite no source and still list
  viz_types removed in Superset 5 (`basic-charts-params.ts:52,79,126,206`).
- Builds a naive `query_context` fallback with an operator-precedence bug that drops `metrics`
  (`chart-client.ts:170-190,184,237`); `setChartFilters` rewrites `query_context` filters but not
  `params` (`:211-256`).
- Dataset metric helper reads the list, whitelists keys and PUTs the full list (`metrics-client.ts:29-70`).
- CI only builds and packs; no tests.

### `braislchao/superset-ai`

- LangGraph agent and CLI over an async httpx client with tenacity (`api/client.py`), pydantic v2
  schemas, pydantic-settings with `SecretStr`.
- One flat `ChartParams` model for 16 chart types (`schemas/charts.py:109-215`); several `viz_type`s are
  not valid in 6.1.0 (`dist_bar`, `line`, `area`, `heatmap`, `histogram`; `schemas/charts.py:13-28`);
  `model_dump(exclude_none=True)` writes every boolean default into every chart.
- One generic `build_query_context` for all types (`schemas/charts.py:781-892`): no `post_processing`,
  legacy `granularity` instead of `x_axis`, `metrics` where ECharts plugins use singular `metric`. Charts
  are created by POST then a second PUT with `query_context`; a failed PUT is only logged
  (`api/charts.py:103-117`).
- Layout generators for stacked, N-column grid and tabbed dashboards (`schemas/dashboards.py:192-371`),
  idempotent `add_charts` and remove-chart that prunes empty rows (`:405-546`); ancestor `parents`
  incomplete (`:337,345`); native filter scope by chart IDs documented but unused (`:620,641`).
- `find_or_create` for datasets (`api/datasets.py:145-190`); session login silently falls back to JWT
  (`api/auth.py:154-169`); POST retried on timeout (`api/client.py:143-148`); all schemas use
  `extra="ignore"` (`schemas/common.py:11`).
- Tests mocked (respx); the compose stack runs Superset 3.1.0.

### `opus-42/superset-api-client` and `ishahroz/superset-python-client`

- Generic dataclass `Object`/`ObjectFactories` CRUD (`supersetapiclient/base.py:48,123`), fields from
  `/_info` `add_columns`/`edit_columns` (`:138-150`); `params` untyped.
- `save()` sends only `edit_columns`, which for charts in recent Superset is just `slice_name`, so chart
  params are silently not saved (`base.py:113-117`); `null` JSON fields become `{}` (`:87-89`);
  `Chart.to_json` always sends `dashboards`, overwriting associations (`charts.py:21-23`).
- `ishahroz` adds guest tokens (`client.py:267`), embedded dashboards and copy (`dashboards.py:72-98`),
  CSS templates and JWT-expiry pre-checks.
- **Lineage.** This library's first commit (`f0785f4`, 2025-01-15) still ships the `supersetapiclient`
  package with opus-42's README header and badges; `LICENSE`, `CONTRIBUTING.md`, `scripts/release.sh` and
  `examples/change_colors.py` were byte-identical. `Object`/`ObjectFactories` later became
  `SerializableModel`/`ApiModelFactories` (`supersetapiplus/base/base.py`).

## Cross-cutting comparison

| Aspect | superset-api-plus | Superset `mcp_service` | Preset CLIs | Community MCPs | superset-ai | opus-42 / ishahroz |
|---|---|---|---|---|---|---|
| Usable as remote Python client | yes | no (in-process) | helper client, untyped | no (MCP tools) | async, agent-oriented | yes, untyped |
| Chart model | class per viz_type mirroring native `params` | abstract pydantic configs mapped to `form_data` | opaque `params` | raw JSON (zod docs in Winding) | one flat model | `dict` |
| Allowed values | enums traced to 6.1.0 sources, conformance tests | inline `Literal`s | — | hand-written, stale | hand-written | — |
| `query_context` | client-side buildQuery port checked against frontend captures | not stored; built server-side | stored one reused | passed through or naive | generic, wrong per plugin | never sent |
| Layout | free builder (tabs, rows, columns, markdown, header, divider) | fixed placement + full validator | YAML pass-through | append/remove or none | 3 generators | none |
| Native filters | builder, scopes computed from layout | select/range/time/timegrain, scope by chart IDs, data mask | pass-through | CRUD, static scopes | partial | none |
| Round trip | lossless | rejects unknown input; update overlays | pass-through | lossy updates | `extra="ignore"` | lossy |
| Auth | JWT + refresh, session/CSRF mode | server-side verifier | re-login, Preset tokens | mixed; some broken | session→JWT fallback | JWT (+CSRF) |
| Retries | idempotent methods only, timeouts | n/a | all methods, `https` only | 401/CSRF retry | all methods incl. POST | none |
| Tests | real Superset 6.1.0 + generated fixtures | mocks | mocks | mocks or none | mocks | container / mocks |

## License notes

| Project | License | Reuse of code |
|---|---|---|
| Apache Superset | Apache-2.0 | allowed with attribution; it is already our source of truth |
| opus-42, ishahroz | Apache-2.0 | allowed with attribution (this library derives from opus-42) |
| bintocher, aptro, Winding2020, superset-ai | MIT | allowed with attribution |
| Preset `backend-sdk` | "Copyright (c) 2022 Preset Inc. All rights reserved." | no; ideas only |
| Preset `superset-sup` | BSL 1.1 (non-production use, derivatives inherit BSL) | no; ideas only |

## Limitations

- Code was read, not run; behavior claims about other projects come from their source at the listed
  commit, not from execution.
- The Superset checkout was sparse: claims about `superset.common.form_data_query_context` and the MCP
  unit tests rely on references from `mcp_service`, not on reading those files.
- GitHub and PyPI search may miss projects without English descriptions or under unrelated names.

## Sources

- Repositories and commits listed in [Inventory](#inventory).
- [Superset docs — Using AI with Superset](https://superset.apache.org/user-docs/using-superset/using-ai-with-superset/)
- [Preset — The Preset CLI](https://docs.preset.io/the-preset-cli)
- [Preset blog — Meet `sup!`](https://preset.io/blog/meet-sup-supersets-new-cli-for-automation-and-agents/)
- [Preset blog — Managing Superset assets as code](https://preset.io/blog/version-control-superset-charts-dashboards-superset/)
- PyPI: [`preset-cli`](https://pypi.org/project/preset-cli/), [`superset-sup`](https://pypi.org/project/superset-sup/),
  [`mcp-superset`](https://pypi.org/project/mcp-superset/), [`superset-ai`](https://pypi.org/project/superset-ai/),
  [`superset-api-client`](https://pypi.org/project/superset-api-client/),
  [`superset-python-client`](https://pypi.org/project/superset-python-client/)

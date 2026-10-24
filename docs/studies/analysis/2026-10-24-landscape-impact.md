---
title: "Impact of the client landscape on superset-api-plus"
type: analysis
audience: human+ai-agent
updated: 2026-10-24
cutoff: 2026-10-24
confidence: 0.85
tldr: |
  The landscape study confirms the library's niche and its main design rules (typed models,
  values traced to Superset sources, derived query_context, lossless round trip, retries of
  transient failures on idempotent methods only, tests against a real server). Re-checking our
  code against what the other projects handle surfaced five defects (inconsistent license,
  exception hierarchy, dataset-less time filter, root-only filter scope, unsafe YAML loader)
  and a prioritized list of improvements, led by
  dashboard layout validation and native filter scopes taken from Superset's own MCP service.
tags: [analysis, superset, ecosystem, roadmap, defects]
related:
  - docs/studies/research/2026-10-24-superset-client-landscape.md
  - AGENTS.md
---

# Impact of the client landscape on superset-api-plus

Based on [research/2026-10-24-superset-client-landscape.md](../research/2026-10-24-superset-client-landscape.md).
Paths of this repository refer to commit `10f4159`; external paths to the commits listed in the research.

## TL;DR

- **Keep going.** No other project covers the niche (see research). The rules in `AGENTS.md` are exactly
  where the other projects fail: their defects are legacy `viz_type`s, wrong generic `query_context`,
  lossy updates, POST retries and broken token refresh, all caught only by testing against a real server.
- **Five defects confirmed in our code** (section 1). The license inconsistency needs a maintainer
  decision; the other four are local fixes, each with a test.
- **Top improvements** (section 2): layout depth/cycle/size validation and native filter scope by chart
  IDs, both available as reference rules in Superset's `mcp_service`; CSRF renewal; export batching.
- **Watch Superset master.** It is moving to charts saved without `query_context` and to new aggregates
  and chart types; the next version bump must re-check these.

## 1. Defects confirmed in our code

Each item was re-checked in this repository; the "how found" column names the project whose code
prompted the check.

| # | Defect | Evidence in this repository | How found | Proposed fix |
|---|---|---|---|---|
| D1 | **License is inconsistent.** `LICENSE` is Apache-2.0 (inherited from opus-42), while `pyproject.toml:10`, `setup.py:27` and the README badge/section (`README.md:3,225`) say MPL-2.0 and `setup.cfg:13` says MIT. There is no `NOTICE` or README credit to opus-42. | files listed | lineage check against `opus-42/superset-api-client` | Maintainer decision: pick one license, align all four places and credit the upstream project as Apache-2.0 requires for the derived parts. |
| D2 | **`ComplexBadRequestError` is not a `BadRequestError`.** It subclasses `HTTPError` (`supersetapiplus/exceptions.py:73`), and `raise_for_status` checks a body `errors` list before the status code (`supersetapiplus/utils/request_handler.py:157-158`). A 401/403/404/422 whose body carries `errors` (the SIP-40 shape Superset uses for security and data errors) is neither `UnauthorizedError`/`ForbiddenError`/... nor catchable as `BadRequestError`, contrary to `AGENTS.md` ("all subclasses of `BadRequestError`"); a 401 in that shape would also skip the JWT renewal in `client.py:143`. | lines cited | bintocher error flattening (`client.py:75-110`) | Make the status-specific class win and carry `errors` (or make `ComplexBadRequestError` a `BadRequestError` subclass); integration test with a 403 from `/api/v1/chart/data` for a user without access. |
| D3 | **A time native filter cannot be created without a dataset.** `filter_config` always calls `dataset_target(dataset, column)`, which raises `TypeError` when `dataset` is `None` (`supersetapiplus/dashboards/native_filters.py:83,106`). Superset saves `filter_time` with `targets: [{}]`. | lines cited | Superset `mcp_service/dashboard/tool/manage_native_filters.py:371-377` | Accept `dataset=None` for `filter_time` and emit `[{}]`; integration test that saves and reloads the dashboard. |
| D4 | **Native filter scope is root-only.** `filter_config` always writes `root_scope()` (`native_filters.py:58,109`); there is no way to restrict a filter to some charts. | lines cited | Superset `manage_native_filters.py:264-283` | `scope_chart_ids=[...]` (and/or `excluded=[...]`) mapped to `{"rootPath": ["ROOT_ID"], "excluded": [...]}`; `update_native_filter_scopes` already derives `chartsInScope` from it. |
| D5 | **Exported YAML is parsed with `yaml.FullLoader`** (`supersetapiplus/base/base.py:1110`). | line cited | Preset safe-loading practice | Use `yaml.safe_load`; Superset exports plain YAML. |

## 2. Improvement opportunities

Priority reflects value for users of the library and fit with the current roadmap; "source" is where the
rule or technique can be checked (code from Preset projects is not reusable, see research, License notes).

### High

| # | Opportunity | Our file | Source to check |
|---|---|---|---|
| H1 | Layout validation: parent/child **depth** rules (ROW only up to depth 4, TAB children ROW/COLUMN/TABS up to depth 3), cycle detection, also for layouts loaded from Superset | `supersetapiplus/dashboards/layout.py` (`_ALLOWED_CHILDREN`, `_row_for`) | Superset `dashboard/layout_validation.py:34-90,203-323` (port of frontend `isValidChild.ts`) |
| H2 | Size limits: width 1–12 per component, row height 5–100 units; today only the row budget is checked (`layout.py:251-262`) and `height` is not validated | `layout.py:230-249` | Superset `dashboard/constants.py:27-30` |
| H3 | Renew the CSRF token once on "CSRF token missing/expired" (400) and retry the request; today it is fetched once (`security/csrf.py`, `client.py:117,128`) | `client.py`, `security/csrf.py` | bintocher `client.py:160-172,322-337` |
| H4 | Default value of a select filter turned into `defaultDataMask` (`extraFormData.filters` with `IN`), with the frontend's constraints | `dashboards/native_filters.py` | Superset `manage_native_filters.py:120-170` (`getSelectExtraFormData`) |
| H5 | `filter_range` requires a numeric target column; warn when a filter column is missing from a chart's dataset in scope | `dashboards/metadata.py:71` | Superset `manage_native_filters.py:449`; bintocher `tools/dashboards.py:120-138` |

### Medium

| # | Opportunity | Our file | Source to check |
|---|---|---|---|
| M1 | More chart models, with 6.1.0 names from `tests/fixtures/superset_enums_6.1.0.json`: `echarts_timeseries_line` (already in `BUILD_QUERY`), `echarts_area`, `big_number`, `funnel`, `gauge_chart`, `treemap_v2`, `bubble_v2`, `histogram_v2`, `heatmap_v2`, `sunburst_v2` | `supersetapiplus/charts/`, `build_query.py:801` | Superset `chart/plugins/*` (`native_viz_types`), UI captures via `bin/scripts/` |
| M2 | Export in batches with ZIP merge (today one request with all IDs) | `base/base.py:1097` | Preset `superset.py:816-838` (idea only) |
| M3 | Import in dependency order with continue-on-error; SSH tunnel password/key fields beside `passwords` | `assets.py`, `base/base.py:1153` | Preset `sync/native/command.py:440-616` (idea only); Superset import API |
| M4 | Dataset metric and calculated-column helpers (read list, merge, PUT whole list), `refresh`, `duplicate`, `get_or_create`; `Dataset.to_json` currently drops `columns` (`datasets.py:46-48`) | `supersetapiplus/datasets.py` | Winding `metrics-client.ts:29-70`; bintocher `tools/datasets.py:158-340`; superset-ai `api/datasets.py:145-190` |
| M5 | Typed SIP-40 error fields (`error_type`, `level`, `extra`, issue code messages) and a readable `__str__` (goes with D2) | `exceptions.py` | bintocher `client.py:75-110` |
| M6 | One-call layout presets (`grid(charts, columns)`, `tabbed({"Tab": [...]})`), idempotent add, remove-chart that prunes empty rows | `dashboards/layout.py` | superset-ai `schemas/dashboards.py:192-546` |
| M7 | Helpful error for removed `viz_type`s (`bar`→`echarts_timeseries_bar`, `dist_bar`, `line`, ...) in `Chart.get_class` | `charts/charts.py` | bintocher `tools/charts.py:36-57` |
| M8 | Lazy pagination iterator next to `find_all` | `base/base.py:1018` | Preset `superset.py:465-483` (idea only) |

### Low / later

| # | Opportunity | Note |
|---|---|---|
| L1 | Metric shape rules (`sql_expression` excludes `aggregate`/`saved_metric` and needs `label`), filter value cardinality per operator | cross-check `charts/metric.py`, `charts/filters.py` with Superset `chart/schemas.py:957-1160` |
| L2 | Box plot whiskers: accept custom `"<low>/<high> percentiles"` besides the four presets (`charts/types.py`, `WhiskerOptions`) | frontend `PERCENTILE_REGEX` |
| L3 | Reject moment.js tokens in `*_format` fields | bintocher `tools/charts.py:226-237` |
| L4 | Guest token, embedded dashboard, dashboard copy, CSS templates | ishahroz `client.py:267`, `dashboards.py:72-98` |
| L5 | Optional async transport (httpx) keeping the retry rule (transient failures on idempotent methods only, 429 on any method) | superset-ai `api/client.py:42-68`; fits the planned `transport/` package |
| L6 | Preset workspace auth (API token → JWT) as an extra auth strategy | Preset `auth/preset.py` (idea only) |

## 3. Design choices the landscape confirms

| Choice in `AGENTS.md` | What happens in projects without it |
|---|---|
| Fields from OpenAPI, not `/_info` | opus-42 `save()` sends only `/_info` `edit_columns`, so chart `params` are silently not saved |
| Allowed values traced to the pinned Superset source, checked by scripts | Winding and superset-ai advertise `viz_type`s removed in Superset 5 |
| `query_context` derived by a buildQuery port checked against the frontend | superset-ai's generic query lacks `post_processing` and uses `granularity`; bintocher and Winding leave `params` and `query_context` out of sync |
| Lossless round trip (`MissingField`, preserved extra keys) | superset-ai `extra="ignore"` and boolean-default pollution; opus-42 turns `null` into `{}` |
| `chart.save()` does not send `dashboards` | opus-42 overwrites dashboard associations on every save |
| Transient failures retried only on idempotent methods; 429 (request not processed) on any method | superset-ai retries POST on timeout, which can create duplicates; Preset retries every method on connection and read errors |
| TLS verified by default | Preset resends after re-auth with `verify=False` |
| Never store or log secrets | aptro writes the JWT in plaintext next to the code |
| Server behavior tested against the real Superset | every other project uses mocks only, and each has defects a live test would catch |

## 4. Points to watch on the next Superset version

- Superset master saves MCP-created charts **without** `query_context` and rebuilds queries server-side
  (`form_data_query_context`). If that becomes the norm, `derive_query_context()` may become optional for
  saving; keep an integration test that a chart saved without `query_context` still serves
  `/api/v1/chart/data` and thumbnails on the pinned version.
- New aggregates (`STDDEV_SAMP`, `VAR_SAMP`, `MEDIAN`, `PERCENTILE`) and pivot aggregate `"Metric"` exist
  on master only; they enter our enums when the fixtures are regenerated for a version that ships them.
- `mcp_service/chart/schemas.py` is a maintained, upstream description of chart configs. Adding it as an
  extra cross-check in `bin/scripts/extract_superset_enums.py` is cheaper than re-deriving the same rules
  from control panels by hand.

## 5. Not adopted

- Depending on any of these projects: the MCP service needs the Superset process; Preset code is not
  reusable (proprietary / BSL); the MIT projects are lower in fidelity than this library.
- Abstract chart configs (`chart_type: "xy"`) instead of native `params`: they cannot round-trip charts
  created in the UI. They could be offered later as a convenience layer on top of the native models.
- Silent auth fallbacks, retries on POST, hidden mutation of other objects (bintocher sets
  `always_filter_main_dttm` on datasets when adding a filter).

---
title: "Follow-up audit: layout rules, server error shapes and value sets"
type: analysis
audience: human+ai-agent
updated: 2026-10-24
cutoff: 2026-10-24
confidence: 0.85
tldr: |
  Three checks prompted by the landscape study. (1) Layout: builder output respects the frontend's
  isValidChild depth rules, but sizes are not validated (width 0 or negative, any height accepted)
  and validate() only checks dangling children. (2) Error shapes on a live 6.1.0: 404s carry
  {"message"}, CSRF failures are 400 with SIP-40 "errors", JWT errors carry {"msg"} (422 for a
  malformed token), so the library loses the JWT error text. (3) Value sets: our enums agree with the
  6.1.0 backend; Superset's own MCP service in 6.1.0 accepts four aggregates the 6.1.0 backend cannot
  execute, which confirms sourcing values from the backend and frontend code.
tags: [analysis, audit, layout, errors, enums, superset-6.1.0]
related:
  - docs/studies/research/2026-10-24-superset-client-landscape.md
  - docs/studies/analysis/2026-10-24-landscape-impact.md
---

# Follow-up audit: layout rules, server error shapes and value sets

Library at commit `58dde47`; Superset 6.1.0 (tag) for sources; live checks on the test stack
(`docker compose -p superset-api-plus`, image 6.1.0, no examples loaded).

## 1. Dashboard layout vs the frontend contract

**Reference.** `superset-frontend/src/dashboard/util/isValidChild.ts` (6.1.0) admits a child only when
its type is listed for the parent and the parent's depth is at most the listed value; `TABS` and `TAB`
render children at their own depth, every other container increments it (same reading as the port in
`superset/mcp_service/dashboard/layout_validation.py`). Size limits come from
`superset-frontend/src/dashboard/util/constants.ts:40-43`: 12 columns, `GRID_MIN_COLUMN_COUNT = 1`,
`GRID_MIN_ROW_UNITS = 5`, `GRID_MAX_ROW_UNITS = 100`.

**Method.** A scratch script built layouts with the public builder (`DashboardLayout.empty`, `add_tabs`,
`add_tab`, `add_row`, `add_chart`, `add_markdown`, `add_header`, `add_divider`) and checked them with a
Python reading of the table above.

| Case | Result |
|---|---|
| Flat grid (chart, markdown, header, divider) | valid |
| `TABS > TAB > ROW > CHART`, header in a tab | valid |
| Nested tabs, two and three levels | valid (tabs do not consume depth) |
| `TABS` under a `ROW` | rejected by the builder, as in the frontend |
| `add_chart(width=0)`, `width=-3` | **accepted** |
| `add_chart(height=0)`, `height=1`, `height=500` | **accepted** |
| Loaded layout with `TAB > CHART` and `TAB > COLUMN` (allowed by the frontend) | loaded and edited without error |

Findings:

- **A1 (defect).** Component sizes are not validated: `add_chart`/`add_markdown`
  (`supersetapiplus/dashboards/layout.py:230-249`) accept widths below 1 and heights outside 5–100; only
  the row budget of 12 columns is enforced (`_row_for`, `layout.py:251-262`). Superset does not validate
  `position_json` on save, so the dashboard is stored with sizes the editor cannot produce.
- **A2 (gap).** `DashboardLayout.validate()` (`layout.py:137-141`) only checks that children exist: no
  type rules, depth rules, cycles or `parents` consistency. Layouts loaded from Superset are never
  checked.
- **A3 (note).** `_ALLOWED_CHILDREN` (`layout.py:57`) is stricter than the frontend for what the builder
  creates (charts and markdown always go into a `ROW`, as the editor does); there is no `add_column`.
  Because the table is used only for components the library adds, loaded layouts with frontend-valid
  shapes such as `TAB > CHART` remain editable.

## 2. Error responses of a live Superset 6.1.0

Read-only requests (no object created) with an admin JWT unless noted:

| Request | Status | Body shape |
|---|---|---|
| `GET /api/v1/chart/999999`, `GET /api/v1/dataset/999999`, `GET /api/v1/chart/999999/data/` | 404 | `{"message": "Not found"}` |
| `POST /api/v1/chart/data` with an unknown datasource | 404 | `{"message": "Not found"}` |
| `POST /api/v1/chart/data` with `queries` not a list | 400 | `{"message": "Request is incorrect: {...}"}` |
| `GET /api/v1/chart/?q=(bad` | 400 | `{"message": "Not a valid rison/json argument"}` |
| `PUT`/`POST`/`DELETE` with JWT but without `X-CSRFToken` | 400 | SIP-40: `{"errors": [{"message": "400 Bad Request: The CSRF token is missing.", "error_type": "GENERIC_BACKEND_ERROR", "level": "error", "extra": {"issue_codes": [...]}}]}` |
| Any endpoint with a malformed bearer token | 422 | `{"msg": "Not enough segments"}` (flask-jwt-extended) |

Findings:

- **E1 (defect).** JWT errors use the key `msg`, not `message`. `raise_for_status`
  (`supersetapiplus/utils/request_handler.py:172`) reads only `message`, so `UnauthorizedError` (expired
  token, 401) and `UnprocessableEntityError` (malformed or wrong-type token, 422) are raised without the
  server's explanation. A malformed or refresh-instead-of-access token surfaces as a 422 "unprocessable
  entity", not as an authentication error.
- **E2 (supports H3 of the landscape analysis).** A missing or expired CSRF token is a 400 with a SIP-40
  body whose message contains "CSRF token"; this is the reliable trigger for a one-time CSRF renewal and
  retry. Today it becomes `ComplexBadRequestError`.
- **E3 (context for D2).** In these checks only 400 responses carried `errors`; 404s did not. Whether
  401/403 responses carry `errors` depends on the endpoint (security exceptions on data endpoints); the
  fix of D2 makes the status-specific class win regardless of the body, which covers both shapes. A 403
  probe needs a restricted user, left to the integration tests of that fix.

## 3. Value sets: library enums vs Superset's MCP service (6.1.0)

`superset/mcp_service/chart/schemas.py` at tag 6.1.0 declares `Literal` value sets for the chart
configs it accepts. Compared with `tests/fixtures/superset_enums_6.1.0.json`:

| Set | MCP service 6.1.0 | Library (source) | Assessment |
|---|---|---|---|
| Simple metric aggregate | `SUM, COUNT, AVG, MIN, MAX, COUNT_DISTINCT, STDDEV, VAR, MEDIAN, PERCENTILE` (`schemas.py:507`, `chart_utils.py:487-497`) | `AVG, COUNT, COUNT_DISTINCT, MAX, MIN, SUM` (`src/explore/constants.ts` AGGREGATES) | **Library is right.** The 6.1.0 backend executes SIMPLE metrics through `sqla_aggregations` with only the six keys (`superset/models/helpers.py:805-812,2110`); the four extra values raise `KeyError` at query time. Superset master later maps them to `STDDEV_SAMP`/`VAR_SAMP` and adds backend support. |
| Pie label type | 7 values, no `template` (`schemas.py:652`) | 8 values incl. `template` (`EchartsPieLabelType`) | Subset; library complete. |
| Pivot aggregate function | 11 values (`schemas.py:697`) | 18 values incl. `List Unique Values` and the "as Fraction of" family (`controlPanel` choices) | Subset; library complete. |
| Simple filter operator | 11 values (`schemas.py:578`) | 17 backend `FilterOperator` values incl. `IS NULL`, `IS TRUE`, `NOT ILIKE`, `TEMPORAL_RANGE` | Subset; library complete. |
| Legend position, orientation, query mode | same values | same values | Agree. |

Conclusion: no value in our enums is contradicted by the upstream MCP service, and its one superset
(extra aggregates) is a value the same Superset release cannot execute. Hand-maintained value sets drift
even inside Superset itself; values must keep coming from the code that executes or renders them
(backend enums, frontend constants and control panels), as `bin/scripts/extract_superset_enums.py` does.

## Disposition

| Finding | Type | Goes to |
|---|---|---|
| A1 sizes not validated | defect | library maintainers (fix with test) |
| E1 JWT `msg` lost; malformed token not an auth error | defect | library maintainers (fix with integration test) |
| A2 structural `validate()` | improvement | feature backlog (layout validation) |
| E2 CSRF renewal trigger | improvement | feature backlog (transport robustness) |
| A3, E3, section 3 | notes | none |

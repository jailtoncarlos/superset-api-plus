# Superset 7.0 migration (branch `superset-7`)

Changes of the `superset-7` branch, which prepares superset-api-plus 3.0.0 for Superset 7.0. `main` keeps the
Superset 6.1 line (releases 2.x) and is merged into this branch after every change, so this file lists only what
the branch adds. When Superset 7.0.0 final is out, the branch is merged into `main` and this list becomes the
3.0.0 entry of CHANGELOG.md (task #73).

Plan, impact and decisions: `docs/studies/analysis/2026-11-24-superset-7.0-impact-and-migration.md`; feature #53.
Validation: the test stack runs the newest Superset 7.0 release (`7.0.0rc3` today) with the example dashboards
(`SUPERSET_LOAD_EXAMPLES=1`, `tests/integration/test_examples/`) once #66 moves it there.

## Changed

* Target: Superset 7.0. `client.server_version` warns (`UnsupportedServerVersionWarning`) on a server whose major
  version is not 7; version `3.0.0.dev0` until the release (#85).

## Added

* Superset 7.0 excerpts `tests/fixtures/superset_openapi_7.0.0rc3.json` and `superset_enums_7.0.0rc3.json`, generated
  by the extractors from the `7.0.0rc3` tag. The enum extractor reads the calendar plugin from
  `plugins/plugin-chart-calendar` and drops `pivot_table_v2.aggregateFunction` from 7.0 on, and leaves out of
  `migrated_viz_types` the migrations behind a feature flag (`table` → `ag-grid-table`); the 6.1.0 excerpts it
  regenerates are unchanged. The conformance tests still read the 6.1.0 excerpts until the models move to 7.0
  (#55).
* Subjects: `client.subjects` (read-only, `/api/v1/security/subject/`) with `for_user`, `for_role` and `for_group`,
  the `Subject` model and the `SubjectType` enum (`superset/subjects/types.py`, in the enum extractor from 7.0 on),
  the principal that editors, viewers and row level security rules refer to in 7.0 (#56).

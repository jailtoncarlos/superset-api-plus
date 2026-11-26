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
* The OpenAPI conformance checks the requests against the 7.0.0rc3 specification. The fields 7.0 added that the
  library does not model yet (`uuid`, dashboard `description` and `theme_id`, dataset `currency_code_column`...) are
  listed in the test until #69.

## Deprecated

* `owners` (users) on charts, dashboards and datasets, and a dashboard's `roles`: the fields Superset 7.0 replaced
  with `editors` and `viewers`; `roles` on row level security rules, replaced with `subjects` (and `users`). They
  still work: before sending, their users and roles are turned into subjects, with a `DeprecationWarning`. As on
  Superset 6.1, assigning them replaces the list (a role left out loses its access; an empty list clears it),
  keeping the subjects the code itself put in the new field; RLS `users` adds (#57, #58, #59).

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
* Editors and viewers: charts, dashboards and datasets have `editors`, and charts and dashboards `viewers` (with the
  `ENABLE_VIEWERS` feature flag; without it Superset refuses to add viewers, `UnprocessableEntityError`): subjects,
  read as objects and sent as ids (#57, #58).
* Soft delete (`SOFT_DELETE`, on by default in 7.0): a deleted chart, dashboard or dataset is archived.
  `find_archived()`, `restore(uuid)` and `purge(uuid)` on `client.charts`, `client.dashboards` and `client.datasets`
  (a dataset is purged with the impact token of `purge-impact`); the three models read their `uuid`. `get_or_create`
  of a table whose dataset is archived raises `UnprocessableEntityError` naming it. The integration tests purge what
  they archive, so a database can be deleted and a second run reuses the names (#65).
* Row level security rules name `subjects`; `users` takes users, sent as their subjects. A Regular rule without any
  subject is refused before sending, as Superset 7.0 requires one (#59).

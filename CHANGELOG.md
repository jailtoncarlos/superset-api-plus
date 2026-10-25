# CHANGELOG

## Unreleased

Compatibility with Superset 6.1.0, charts and dashboards built in code as the UI builds them, and a
reorganized, tested package.

### Added

* Superset 6.1.0 support: login-form session mode with CSRF (`enable_session_mode()`), JWT renewal on a
  rejected token, `POST /api/v1/sqllab/execute/`, multipart import, paginated `find_all()` and `count()`.
* CSS templates: `client.css_templates` (`CssTemplate`: `template_name`, `css`).
* Export in batches (`export(ids, path, batch_size=N)`, merged into one bundle), lazy pagination
  (`iter_all()`), and `client.bundle_import.import_objects()`: one import per object of a bundle, in
  dependency order, with a checkpoint file and continue-on-error.
* Dashboards: `DashboardLayout` builder for `position_json` (tabs, rows, columns, markdown, charts, headers,
  dividers; `add_chart_grid()` and `add_chart_tabs()` presets, `remove_chart()` pruning empty rows), native filters with dependencies, chart scopes and dataset-less time filters, owners and
  roles, `Dashboards.copy()`, `client.dashboard_charts`. Layouts are checked against the dashboard renderer
  rules before sending (`layout.problems()`, `layout.validate()`, `LayoutWarning` for layouts read from
  Superset). Select filters take a `default_value` (saved as the editor's `defaultDataMask`); the filter
  column is checked against a dataset read from Superset (numeric for range filters), and
  `client.dashboard_charts.native_filter_problems()` reports filter columns missing from the datasets of
  the charts in scope.
* Charts: the frontend `buildQuery` ported (`charts/build_query.py`), so charts built in code store the
  `query_context` Explore derives; UI defaults for new charts; `derive_query_context()`. New models:
  `treemap_v2`, `echarts_timeseries_line`, `echarts_area`, `big_number` (with trendline), `funnel`,
  `gauge_chart`, `sunburst_v2`, `heatmap_v2`, `bubble_v2` and `histogram_v2`.
* Datasets: saved metrics (`add_metric()`) and calculated columns (`add_calculated_column()`), merged by name
  and sent whole (Superset deletes the ones left out), `refresh()`, `duplicate()`,
  `client.datasets.get_or_create()`, time column and the other update fields; databases: the Superset 6
  connection fields; `delete_many()` on every resource.
* Quality gates: complexity ratchet, OpenAPI and source-code conformance, model attribute checks and layer
  contracts as pre-commit hooks; integration tests against a real Superset in CI. The excerpts of the
  Superset sources record their provenance (tag, commit, paths) and their extractors fail on a missing symbol.

### Fixed

* Superset errors with a SIP-40 body (`{"errors": [...]}`) or a JWT `{"msg": ...}` body are mapped to the
  status exceptions; rate-limited requests (429) are retried.
* Long-lived clients: an expired CSRF token or session-mode login is renewed once and the request sent again
  (it used to fail with "The CSRF token is missing." or a 401). SIP-40 errors are typed
  (`error.superset_errors`) and `str(error)` is their messages instead of a JSON dump.
* Objects read from Superset are written back without loss (absent keys stay absent, null JSON stays
  null), including charts whose stored `query_context` differs from older Superset versions.
* Enum values aligned with the Superset source (aggregates, operators, title positions, stacking...).
* Chart inputs Superset would reject or silently change are rejected in code: removed viz types name their
  replacement (`bar` -> `echarts_timeseries_bar`...); a SQL metric takes no column or aggregate and needs a
  label (single-metric charts now take SQL metrics); IN/NOT IN filters store a list, IS ... filters no value,
  and the other operators reject a list (Superset kept only its first item); box plot whiskers accept custom
  `"<low>/<high> percentiles"`; time formats reject moment.js patterns, which Superset 6 shows as text.
* Secrets are masked in logs; TLS is verified by default.
* Chart builders: a pie with a SQL-expression metric validates; `add_simple_filter` works on a chart read
  without `adhoc_filters`; a chart whose stored `query_context` is null is edited through its params.
* Forecast options of the derived query context follow `parseInt`/`parseFloat`: a missing or non-numeric
  `forecastInterval` no longer raises, and NaN is written as `null` (it produced invalid JSON).
* Serialization: integer enums set in code are written as numbers (`LabelRotation.FORTY_FIVE` was sent as
  `"45"`, a column's `type_generic` as `"1"`), and fields are written in declaration order (the order changed
  from one Python process to the next, and the query of some plugins follows the form_data key order).

### Changed

* Models move to pydantic v2 (new runtime dependency `pydantic>=2.12`), keeping `from_json`, `to_dict`,
  `to_json` and `validate` and what the library writes: values Superset stored are read without conversion or
  loss, absent keys stay absent, unmodeled keys are kept. Migrated so far: the dashboard `json_metadata`
  (`Metadata` and its cross-filter models) and `position_json` (`DashboardLayout`, built with keyword
  arguments: `DashboardLayout(components=...)`).
* The package is organized in layers checked by `import-linter`: `core` (models, no HTTP), `transport`,
  `auth`, `resources`, `dashboards`, `charts`, `services`, `client`. `supersetapiplus` exports the names
  applications use (`SupersetClient`, `Chart`, `Dashboard`, `ChartRef`, `Dataset`, `Database`...); the
  datasets, databases, saved queries and assets modules are implemented in `supersetapiplus.resources` and
  keep their public paths. Charts and dashboards together are handled by `client.dashboard_charts`.

* String enums (`ChartType`, `TimeGrain`, `FilterOperatorType`...) are `str` subclasses: a member equals and
  hashes as its value (`ChartType.PIE == "pie"`) and can be a dictionary key. Before, members were unhashable
  and never equal to strings.
* Model equality is the field-by-field equality of each `@dataclass` (the base class methods were never
  used); unmodeled keys read from Superset (`extra_fields`) belong to each instance and do not take part.

* The client never prompts for credentials: without a username or password, login raises
  `MissingCredentialsError` (it used to call `getpass`, which hangs a DAG or a service).
* `Chart.get_class(viz_type, module)` resolves through an explicit registry (`Chart.for_viz_type`), importing
  `supersetapiplus.charts.<viz_type>` on demand; the module no longer needs to be imported first.

* Packaging: `pyproject.toml` is the only source of dependencies, locked in `uv.lock` (`uv sync --locked
  --all-extras`); `setup.py`, `setup.cfg`, `requirements.txt`, `requirements/` and `pytest.ini` were removed.
  Runtime floors lowered to the lowest versions the suite passes with (`requests>=2.31`, `pyyaml>=6.0.1`,
  `beautifulsoup4>=4.11`...), and `urllib3`, imported directly, is now declared. Installing under the
  Airflow 3.3.2 constraints changes none of their pinned versions.
* Tests no longer hide `DeprecationWarning` (pytest configuration in `pyproject.toml`).
* The package is typed (`py.typed`, PEP 561) and passes `mypy --strict`, checked by a pre-commit hook; only
  the legacy and compatibility modules are exempt.

### Deprecated

Misspelled public names were renamed. The old names keep working as aliases and emit `DeprecationWarning`;
they will be removed in a future major version.

| Old name | New name |
|---|---|
| `supersetapiplus.dashboards.nodeposisition` (module) | `supersetapiplus.dashboards.nodeposition` |
| `supersetapiplus.dashboards.treenodeposisition` (module) | `supersetapiplus.dashboards.treenodeposition` |
| `dashboards.metadataposition.Metadataposition` | `MetadataPosition` |
| `dashboards.dashboards.defult_metadata`, `defult_metadata_position` | `default_metadata`, `default_metadata_position` |
| `dashboards.metadata.GlobalChartconfiguration`, `GlobalChartconfigurationScope` | `GlobalChartConfiguration`, `GlobalChartConfigurationScope` |
| `charts.queries.QuerieExtra` | `QueryExtra` |
| `charts.types.StackStylyType`, `TitlepositionType`, `CurrentPositionType` | `StackStyleType`, `TitlePositionType`, `CurrencyPositionType` |
| `ChartType.PIVOT_TALBE_V2` | `ChartType.PIVOT_TABLE_V2` |
| `LabelType.CATEGORI_VALUE_AND_PERCENTAG` | `LabelType.CATEGORY_VALUE_AND_PERCENTAGE` |
| `FilterOperatorType.NOT_EQUAL` | `FilterOperatorType.NOT_EQUALS` |
| `TimeSeriesBarOption.y_axis()`, `EchartsTimeseriesBarChart.y_axis()` (set the X axis) | `set_x_axis()` |
| `Database.encrypted_extra`, `allow_multi_schema_metadata_fetch` (gone in Superset 6) | `masked_encrypted_extra` / none |
| `charts.types.SqlMapType` (a column type is free text) | `str` |

Modules moved into layers (package reorganization); the old paths keep working with `DeprecationWarning`.
Loggers follow the module names (e.g. `supersetapiplus.transport.http`).

| Old module | New module |
|---|---|
| `supersetapiplus.utils.request_handler` | `supersetapiplus.transport.http` |
| `supersetapiplus.utils.sensitive` | `supersetapiplus.core.masking` |
| `supersetapiplus.utils.dict_utils` | `supersetapiplus.core.dicts` |
| `supersetapiplus.security.csrf`, `security.session_auth` | `supersetapiplus.auth.csrf`, `auth.session` |
| `supersetapiplus.utils.helpers` (unused by the library) | removed in a future major version |
| `supersetapiplus.base.base` | `supersetapiplus.core.model` (`SerializableModel`, `ObjectDecoder`) and `supersetapiplus.resources.repository` (`ApiModelFactories`, `UnsupportedObject`) |
| `supersetapiplus.base.fields`, `base.parse`, `base.sentinels`, `base.enum_str` | `supersetapiplus.core.fields`, `core.parse`, `core.sentinels`, `core.enums` |
| `supersetapiplus.typing` | `supersetapiplus.core.typing` |
| `supersetapiplus.base.types`, `base.datasource` | `supersetapiplus.core.types`, `core.datasource` |
| `supersetapiplus.charts.types` (module) | `supersetapiplus.charts.types` (package split by subject: `formats`, `time`, `filters`, `query`, `viz`; every name still importable from `charts.types`) |
| `supersetapiplus.dashboards.layout` (module) | `supersetapiplus.dashboards.layout` (package; same names) |
| `dashboards.itemposition`, `nodeposition`, `treenodeposition`, `metadataposition`, `generate_graphviz` (tree builder, superseded by `DashboardLayout`) | `dashboards.layout.legacy.items`, `.nodes`, `.tree`, `.metadata_position`, `.graphviz` |

A model not bound to a client (not created through `client.<resource>.add()` nor read with `get()`) raises
`UnboundModelError` on `save()`, `fetch()`, `delete()` and `base_url`, instead of `AttributeError`.


## 1.0.0a1 (2025-04-10)

> Correction (2026): `setup.py`, `setup.cfg`, `requirements.txt` and `pytest.ini`, listed below as removed,
> are still in the repository; `pyproject.toml` is the source of the metadata and dependencies, and those
> files are removed by the migration to uv.

### Refactoring and Packaging Improvements

* **Refactoring of the Packaging and Quality Structure:**
    * Replaced the `setup.py`/`setup.cfg`-based structure with `pyproject.toml`.
    * Added `CHANGELOG.md` to track the version history.
    * Removed legacy files: `setup.py`, `setup.cfg`, `requirements.txt`, `pytest.ini`.
    * Removed local lint scripts (`bin/`) and the `.pylintrc` file.
    * Updated `.pre-commit-config.yaml` with modern tools: `ruff`, `mypy`, `codespell`.
    * Removed `black`, `isort` and `pylint` from pre-commit (replaced by `ruff`).
    * Migrated the `pytest.ini` configuration to `[tool.pytest.ini_options]` in `pyproject.toml`.
    * Added the `T201` (print) and `T100` (pdb) rules to `ruff` to detect leftover debug statements.
    * Simplified the structure to follow modern Python library best practices.

* **Removal of the `requirements` Folder and Migration of Extras to `pyproject.toml`:**
    * Removed the `requirements-dev.txt`, `requirements-testing.txt` and `requirements-packaging.txt` files.
    * Defined the `[project.optional-dependencies]` sections with the "dev" and "test" extras.
    * Enabled installation via `pip install .[dev,test]`.
    * Eliminated redundancy and centralized the configuration in `pyproject.toml`.

* **Preparation of Version 1.0.0a1:**
    * Added `pyproject.toml` with project metadata and linting tools (`black`, `isort`, `mypy`, `ruff`).
    * Bumped the project version to `1.0.0a1` (public alpha release).
    * Added the initial changelog recording the refactoring and main features.

* **Project Renaming and Restructuring:**
    * Renamed the project from `superset-api-client` to `superset-api-plus`.
    * Set the Python package name to `supersetapiclientplus`.
    * Updated all imports in the source code, examples and tests.
    * Replaced old pre-commit tools with `ruff`, `black`, `mypy`, `isort` and `codespell`.
    * Added the files needed for packaging and publishing: `setup.py`, `setup.cfg`, `MANIFEST.in`, `.pylintrc`, `.pypirc`.
    * Organized the requirements by environment (dev, packaging, testing).
    * Updated the project metadata (author, e-mail, keywords, version).
    * Removed unused dependencies from `requirements-packaging`.
    * Prepared the library for publishing on PyPI (version 0.5.0).

* **Creation of README.md:**
    * Added the `README.md` file.

* **Removal of the `MANIFEST.in` file:**
    * Removed because it is no longer needed with the new packaging.


### Continuous Integration

* Updated the `python-package.yaml` workflow:
  * Dropped Python 3.7 support (EOL and incompatible with Ubuntu 24.04)
  * Added versions 3.10, 3.11 and 3.12 to the test matrix
  * Replaced lint tools (`black`, `flake8`, `isort`) with `ruff`
  * Fixed the `supersetapiplus` package name when running tests with `pytest --cov`

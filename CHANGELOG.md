# CHANGELOG

## Unreleased

### Changed

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

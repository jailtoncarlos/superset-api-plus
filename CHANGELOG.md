# CHANGELOG

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

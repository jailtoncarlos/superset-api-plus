# superset-api-plus

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/superset-api-plus)](https://pypi.org/project/superset-api-plus/)
[![pre-commit](https://img.shields.io/badge/code%20style-pre--commit-blue)](https://pre-commit.com/)

> A typed Python client for the Apache Superset REST API: search, read and write charts, dashboards,
> datasets and databases, and build charts and dashboards in code that match what the Superset UI creates.

Target: **Superset 6.1.0** (Flask-AppBuilder 5) · Python **3.10–3.14**.

---

## What it does

- **Charts in code that look like charts made in the UI.** New charts start from the parameters the
  Superset UI gives a new chart, and their `query_context` is derived from `params` by a port of the
  frontend `buildQuery`, so `/api/v1/chart/{id}/data`, reports and alerts see the same query as Explore.
- **Lossless round trip.** Reading an object and saving it back neither loses nor adds data: unmodeled keys
  are preserved and absent keys stay absent.
- **Dashboards**: layout builder (tabs, rows, markdown, charts) that writes `position_json` as the editor
  does, native filters with dependencies and chart scopes, chart association.
- **Both authentication modes**: JWT, and the login-form session (cookie + CSRF) needed by instances whose
  `Public` role has permissions.
- **Conformance checked in CI and pre-commit** against the OpenAPI specification and the Superset source
  (enums, controlPanel choices, UI defaults), and integration tests against a real Superset.

## Supported chart types

| `viz_type` | Class | Notes |
|---|---|---|
| `table` | `charts.table.TableChart` | aggregate and raw modes |
| `pie` | `charts.pie.PieChart` | one metric |
| `pivot_table_v2` | `charts.pivot_table_v2.PivotTableV2Chart` | dimensions go to rows (`groupbyRows`) |
| `echarts_timeseries_bar` | `charts.echarts_timeseries_bar.EchartsTimeseriesBarChart` | `set_x_axis()` |
| `mixed_timeseries` | `charts.mixed_timeseries.MixedTimeseriesChart` | `set_x_axis()`; query B in the `_b` keys |
| `big_number_total` | `charts.big_number_total.BigNumberTotalChart` | one metric, no dimension |
| `word_cloud` | `charts.word_cloud.WordCloudChart` | one metric, one dimension (`series`) |
| `box_plot` | `charts.box_plot.BoxPlotChart` | `add_distribute_across()` |
| `cal_heatmap` | `charts.cal_heatmap.CalHeatmapChart` | legacy plugin; set `granularity_sqla` |

Other viz types are listed as read-only `UnsupportedObject` items, and `get()` on them raises
`UnsupportedTypeError`.

---

## Installation

```bash
pip install superset-api-plus
```

## Connecting

```python
from supersetapiplus import SupersetClient

client = SupersetClient("https://superset.example.org", "username", "password")  # JWT (Bearer token)
client.enable_session_mode()  # cookie + X-CSRFToken: required when the Public role has permissions
```

A long-lived client renews what Superset rejects before processing a request, once per request, and sends
the request again: an expired JWT (refresh token), an expired session (new form login) and an expired CSRF
token. Errors keep the Superset SIP-40 fields typed (`error.superset_errors`: message, `error_type`,
`level`, issue codes), and `str(error)` gives their messages.

TLS certificates are verified by default (`verify=False` only for development). Timeouts and retries come
from `SUPERSET_API_PLUS_*` environment variables (see [Configuration](#configuration-through-environment-variables)).
The client never prompts for credentials: without them, login raises `MissingCredentialsError`.

## Searching and reading

```python
from supersetapiplus import QueryOperator, QueryStringFilter
from supersetapiplus.exceptions import MultipleFound, NotFound

query = QueryStringFilter()
query.add("slice_name", QueryOperator.STARTS_WITH, "Sales")
charts = client.charts.find(query, columns=["id", "slice_name", "viz_type"])  # typed objects, one page
chart = client.charts.find_one(query, full=True)  # NotFound / MultipleFound; full=True loads params
chart = client.charts.get(42)                      # TableChart, PieChart... by viz_type

chart.slice_name = "Sales by region"
chart.save()  # PUT with the fields the API accepts on update
```

`find_all()` walks every page and `count()` returns the total for a filter. The same methods exist on
`client.dashboards`, `client.datasets`, `client.databases`, `client.saved_queries` and `client.css_templates`
(CSS templates, applied to a dashboard through its `css` field).

Datasets:

```python
dataset = client.datasets.get_or_create("sales", database, schema="public")  # physical table
dataset.add_metric("revenue", "SUM(price * quantity)", d3format=",.2f")       # same name: updated
dataset.add_calculated_column("year", "EXTRACT(YEAR FROM sold_at)", type="INTEGER")
dataset.save()                 # metrics and columns are sent whole: Superset deletes the ones left out
dataset = dataset.refresh()    # columns synced with the table
copy = client.datasets.get(virtual_id).duplicate("sales_copy")              # virtual datasets only
```

`add_metric` and `add_calculated_column` need a dataset read with `client.datasets.get` (or returned by
the methods above): only it holds the stored metrics and columns.

Export and import:

```python
ids = [c.id for c in client.charts.iter_all()]       # pages requested as the iteration goes
client.charts.export(ids, "charts.zip", batch_size=50)  # one request per 50 ids, merged into one bundle
client.assets.import_file("charts.zip", passwords={"warehouse": "..."})  # the whole bundle at once
report = client.bundle_import.import_objects("charts.zip", passwords={"warehouse": "..."},
                                             continue_on_error=True, checkpoint="import.json")
report.imported, report.existing, report.failed      # one import per object, databases first
```

## Creating a chart

```python
from supersetapiplus.charts.pie import PieChart
from supersetapiplus.charts.table import TableChart

datasource = client.datasets.get_datasource("sales")  # dataset by table name

pie = PieChart.instance(slice_name="Sales by region", datasource=datasource)
pie.add_simple_metric("count")          # name of a metric saved in the dataset
pie.add_simple_dimension("region")
pie.add_simple_filter("product", "A")
client.charts.add(pie)                  # returns the new id; pie.id is set

table = TableChart.instance(slice_name="Sales table", datasource=datasource)
table.add_custom_metric("Total sales", sql_expression="SUM(sales)")
table.add_simple_dimension("region")
client.charts.add(table)

rows = client.charts.get_chart_data(pie.id)[0]["data"]
```

A chart read from Superset keeps its stored `query_context`; call `chart.derive_query_context()` after
changing its `params` to store the one the UI would derive.

## Building a dashboard

```python
from supersetapiplus import Dashboard
from supersetapiplus.dashboards.native_filters import FilterType

dashboard = Dashboard(dashboard_title="Sales")
client.dashboards.add(dashboard)

layout = dashboard.reset_layout()                # root, grid and title header, as the editor creates them
overview = layout.add_tab("Overview")
layout.add_markdown("## Sales by region", parent=layout.add_row(parent=overview), width=12, height=None)
row = layout.add_row(parent=overview)
layout.add_chart(pie, title="Share by region", parent=row, width=6)   # widths: 1-12 grid columns
layout.add_chart(table, parent=row, width=6)

filters = dashboard.json_metadata
filters.clear_native_filters()
region = filters.add_native_filter("Region", datasource.id, "region")
filters.add_native_filter("Product", datasource.id, "product", parent=region, charts=[table],
                          default_value=["A"])          # selected when the dashboard opens
filters.add_native_filter("Period", filter_type=FilterType.TIME)    # no dataset: time range filter

dashboard.save()
client.dashboards.attach_charts(dashboard)       # associates the charts of the layout with the dashboard
```

For common shapes, `layout.add_chart_grid(charts, columns=3)` places charts in rows of three and
`layout.add_chart_tabs({"Overview": [...], "Details": [...]}, columns=2)` creates one tab per title;
`layout.add_column(parent=row, width=6)` stacks components vertically, `add_chart(..., skip_existing=True)`
does not place a chart twice, and `layout.remove_chart(chart)` removes it with the rows left empty.

Before a dashboard is sent, its layout is checked against the rules of the dashboard renderer (the parent
and child types and nesting depths of the editor, cycles, components outside the tree):
`layout.problems()` lists them and `layout.validate()` raises. A layout built by the library must be valid
to be saved; a layout read from Superset is saved as read, with a `LayoutWarning` when it breaks a rule.

`client.dashboard_charts.add_chart(dashboard, chart, ...)` places a chart and associates it in one call;
`client.dashboards.copy()` copies a dashboard; `delete_many()` removes several objects at once. Dashboards
read from Superset are written back as read: only filters created by the library get recomputed scopes.

## Errors

HTTP errors are mapped by status, whatever the body format: `UnauthorizedError` (401, also a rejected JWT),
`ForbiddenError` (403), `ResourceNotFoundError` (404) and `UnprocessableEntityError` (422), all subclasses of
`BadRequestError`, which carries the server `message` and the `errors` list. Logs mask passwords, tokens,
cookies and connection secrets.

---

## Project structure

The package is organized in layers; a layer imports only the layers below it (checked by `import-linter`):

```
supersetapiplus/
├── client.py      # SupersetClient: authentication and the resource repositories
├── services/      # operations across resources (charts and dashboards together)
├── charts/        # chart models per viz_type, buildQuery port, chart enums (charts/types)
├── dashboards/    # dashboard model, layout (position_json), native filters, json_metadata
├── resources/     # repositories (CRUD over HTTP); datasets, databases, saved queries, assets
├── auth/          # CSRF token and session mode
├── transport/     # HTTP session, retries, error mapping
└── core/          # models and serialization, fields, enums, masking of secrets (no HTTP)
```

Old module paths keep working with a `DeprecationWarning` (see the [CHANGELOG](CHANGELOG.md)).

---

## Development Setup

Dependencies are declared only in `pyproject.toml` (runtime `dependencies` and the `dev`, `test` and `graph`
extras) and locked in `uv.lock`. With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --all-extras        # creates .venv from the lock (Python from .python-version: 3.10)
uv run pytest tests/unit             # unit tests
uv lock --upgrade                    # refresh the lock to the newest allowed versions
uv build                             # sdist and wheel in dist/
```

Without uv, `pip install -e ".[dev,test]"` installs the same extras. If uv reports odd failures (a package
that does not import although its version is right), clear its cache with `uv cache clean`.

**Dependency floors.** The library runs inside an Airflow image installed with the official Airflow
constraints, so the runtime floors are the lowest versions the suite passes with, not the newest ones.
Check both ends after changing a dependency:

```bash
uv sync --resolution lowest-direct --all-extras && uv run pytest tests/unit   # floors
uv sync --locked --all-extras && uv run pytest tests/unit                     # locked (newest)
uv pip install --constraint <airflow constraints URL> .                       # no conflict expected
```

### Pre-commit hooks

Install the hooks once per clone:

```bash
pre-commit install
```

On every commit they run, on the staged files:

- **ruff** (lint, configured in `pyproject.toml`) and **codespell**;
- **line endings**: files are normalized to LF (also enforced by `.gitattributes`);
- **complexity ratchet** (`bin/scripts/complexity_ratchet.py`): a commit is
  rejected when it adds a function with cyclomatic complexity above 10 (ruff C901) or makes an
  existing one more complex (no function of the package is above the limit today);
- **import layers** (`lint-imports`): the layer contracts of `[tool.importlinter]` in `pyproject.toml`;
- **Superset conformance**: request payloads and routes against the OpenAPI specification;
- **model attributes**: every enum declares its source in the Superset code, every `str` field is an enum
  or declared free text, and a new chart gets the params the UI gives it (see below);
- **mypy**: `mypy --strict` on the whole package (the legacy and compatibility modules listed in
  `[tool.mypy]` of `pyproject.toml` are exempt).

### Integration tests (test stack)

`docker-compose.yml` starts a disposable Superset (version set in `.env`, default 6.1.0) plus a
Postgres for test data. All settings come from `.env` (copy `.env.example`; `.env` is not versioned):

```bash
cp .env.example .env            # adjust SUPERSET_SECRET_KEY, credentials, port, version
docker compose -p superset-api-plus up -d --build
SUPERSET_INTEGRATION=1 pytest tests/integration -v
docker compose -p superset-api-plus down -v
```

The suite creates its own database, dataset, charts, dashboard and saved query (prefix
`zz-superset-api-plus-test`) and removes them. To target another instance instead, set
`SUPERSET_URL`, `SUPERSET_USERNAME`, `SUPERSET_PASSWORD` and `SUPERSET_TEST_DATABASE_URI`.

### Configuration through environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SUPERSET_API_PLUS_TIMEOUT_CONNECT` | `10` | connection timeout (s) |
| `SUPERSET_API_PLUS_TIMEOUT_READ` | `20` | read timeout (s) |
| `SUPERSET_API_PLUS_RETRIES` | `3` | retries on transient HTTP errors |
| `SUPERSET_API_PLUS_BACKOFF_FACTOR` | `0.5` | exponential backoff factor |

The examples in `examples/` read `SUPERSET_URL`, `SUPERSET_USERNAME` and `SUPERSET_PASSWORD`.

### Conformance with the Superset OpenAPI specification

`tests/unit/test_openapi_conformance.py` checks the library against an excerpt of the official
Superset OpenAPI specification (`tests/fixtures/superset_openapi_<version>.json`):

- POST/PUT payloads of charts, dashboards, datasets, databases and saved queries only carry
  fields accepted by `{Resource}RestApi.post/.put`, include the required ones and match the
  declared types;
- `POST_FIELDS`/`PUT_FIELDS` declared in each model are exactly the specification fields
  (the `/_info` endpoint is not a reliable source: in 6.1.0 charts report only `slice_name`);
- every route the library calls exists with the method used.

The specification types many fields only as `string`, while the Superset source defines them as
enums. An excerpt of the source (`tests/fixtures/superset_enums_<version>.json`, generated by
`bin/scripts/extract_superset_enums.py <version>`: backend and frontend enums, controlPanel `choices`,
option lists, settings and the Flask-AppBuilder filter operators) backs two checks:

- `tests/unit/test_enum_conformance.py`: every enum of the library declares its source and matches
  the official values (or, for free-form controls such as number formats, offers all of them);
- `tests/unit/test_attribute_types.py`: every `str` field of the models is declared free text with
  the reason; any other field must be typed with an enum.

The `superset-conformance` pre-commit hook runs the OpenAPI checks and the `model-attributes` hook
runs the attribute checks, whenever the library or the excerpts change. To target another Superset
version:

```bash
python bin/scripts/extract_openapi.py <version> > tests/fixtures/superset_openapi_<version>.json
python bin/scripts/extract_superset_enums.py <version> > tests/fixtures/superset_enums_<version>.json
# UI references (needs the test stack with SUPERSET_LOAD_EXAMPLES=1 and SUPERSET_VERSION=<version>):
SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... python bin/scripts/extract_ui_references.py <version>
# UI defaults of a new chart (same stack, plus Playwright): checked by tests/unit/test_ui_defaults.py
SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... python bin/scripts/extract_ui_defaults.py <version>
# point the fixture paths in tests/unit/test_*_conformance.py to the new files, run the tests and
# fix the reported divergences (POST_FIELDS/PUT_FIELDS, payloads, routes, enum values)
```

---

## License

Licensed under the **Apache License 2.0** (see `LICENSE`).

This project started as a fork of [opus-42/superset-api-client](https://github.com/opus-42/superset-api-client),
also licensed under the Apache License 2.0; see `NOTICE` for attribution.

---

## Author

Developed and maintained by **COSINF/DIGTI/IFRN**  
Information Systems Coordination  
Information Technology Management Directorate  
Federal Institute of Rio Grande do Norte

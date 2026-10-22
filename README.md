# superset-api-plus

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/superset-api-plus)](https://pypi.org/project/superset-api-plus/)
[![pre-commit](https://img.shields.io/badge/code%20style-pre--commit-blue)](https://pre-commit.com/)

> A Python library for automating chart and dashboard creation in Apache Superset via its REST API.

---

## Purpose

**`superset-api-plus`** is a high-level client for Apache Superset's REST API.  
It simplifies the programmatic creation of dashboards and charts by abstracting Superset's low-level API details — allowing full automation and integration with data pipelines.

This library was designed to power systems like [suap-analytics](https://github.com/jailtoncarlos/suap-analytics), enabling:

- Declarative creation of dashboards from SQL or metadata
- Dynamic generation of chart layouts and filters
- Full customization of visual properties (e.g., labels, legends, dimensions)
- Export of dashboard layouts to Graphviz (`.svg`, `.gv`)

---

## Key Features

- ✅ Simplified chart creation (pie, table, time series, bar, etc.)
- ✅ Easy API client initialization with credentials or `.env`
- ✅ Dashboard layout modeling via nested tree structure
- ✅ Chart positioning using `TabItemPosition`, `MarkdownItemPosition`, `DividerItemPosition`
- ✅ Graph export: visualize dashboard layout structure in SVG
- ✅ Integration with SQL-based metadata or ETL processes

---

## Installation

```bash
pip install superset-api-plus
```

Or install from source:

```bash
git clone https://github.com/jailtoncarlos/superset-api-plus.git
cd superset-api-plus
pip install .
```

---

## Example Use Case

This example demonstrates how an external system (like `suap-analytics`) can use `superset-api-plus` to generate a Superset dashboard based on metadata from a SQL query:

```python
from supersetapiplus import SupersetClient
from supersetapiplus.charts.pie import PieChart, PieOption
from supersetapiplus.charts.types import MetricType, SqlMapType
from supersetapiplus.charts.queries import AdhocMetricColumn

client = SupersetClient(
    host="https://your-superset-instance",
    username="admin",
    password="admin"
)

datasource = client.datasets.get_datasource("aai_resposta")

chart = PieChart.instance(
    slice_name="Respondents by Answer",
    datasource=datasource,
    options=PieOption(show_total=True)
)

chart.add_custom_dimension(label="Answer", sql_expression="resposta_valor")
chart.add_custom_metric(
    label="Respondents",
    aggregate=MetricType.COUNT_DISTINCT,
    column=AdhocMetricColumn(column_name="respondente_id", type=SqlMapType.INTEGER)
)

chart.add_simple_filter("avaliacao_id", 21)
client.charts.add(chart, title="Example Chart")
```

---

## Real-World Power

Using `superset-api-plus`, an external application can:

- Fetch dashboard structure and metadata from a SQL query
- Build a complete dashboard with multiple levels of nesting:
  ```
  Dashboard
  ├── Axis (Tab)
  │   └── Dimension (Tab)
  │       └── Macroprocess (Markdown + Charts)
  ```
- Dynamically choose the chart type based on metadata (e.g., pie for Likert scale, table for multiple choice)
- Generate and persist the dashboard layout tree structure
- Export `.svg` diagram of the layout using Graphviz

This turns Superset into a **programmable dashboard engine**, ideal for automation in public institutions, analytics platforms, and research dashboards.

---

## Project Structure

```
supersetapiplus/
├── base/              # Low-level request and API abstractions
├── charts/            # Chart definitions and options (pie, table, bar, etc.)
├── dashboards/        # Dashboard layout, positioning, and metadata
├── client.py          # SupersetClient initialization and route binding
```

---

## Development Setup

To install development and testing dependencies using `pyproject.toml` extras:

```bash
# Install development dependencies (linters, tools, debuggers)
pip install .[dev]

# Install testing dependencies
pip install .[test]

# Or install both at once
pip install .[dev,test]
```

### Pre-commit hooks

Install the hooks once per clone:

```bash
pre-commit install
```

On every commit they run, on the staged files:

- **ruff** (lint, configured in `pyproject.toml`) and **codespell**;
- **line endings**: files are normalized to LF (also enforced by `.gitattributes`);
- **complexity ratchet** (`bin/scripts/complexidade-nova.py`, same hook used by SUAP): a commit is
  rejected when it adds a function with cyclomatic complexity above 10 (ruff C901) or makes an
  existing one more complex. Legacy functions already above the limit may be edited as long as
  their complexity does not grow. List them with
  `ruff check --select C901 --config 'lint.mccabe.max-complexity=10' supersetapiplus`.

`mypy` runs only on demand (`pre-commit run mypy --hook-stage manual`) until the codebase passes
`mypy --strict`.

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
`zz-superset-api-plus-teste`) and removes them. To target another instance instead, set
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

`tests/unit/test_conformidade_openapi.py` checks the library against an excerpt of the official
Superset OpenAPI specification (`tests/fixtures/superset_openapi_<version>.json`):

- POST/PUT payloads of charts, dashboards, datasets, databases and saved queries only carry
  fields accepted by `{Resource}RestApi.post/.put`, include the required ones and match the
  declared types;
- `POST_FIELDS`/`PUT_FIELDS` declared in each model are exactly the specification fields
  (the `/_info` endpoint is not a reliable source: in 6.1.0 charts report only `slice_name`);
- every route the library calls exists with the method used.

The `conformidade-openapi` pre-commit hook runs these tests whenever the library or the excerpt
changes. To target another Superset version:

```bash
curl -sL https://raw.githubusercontent.com/apache/superset/<version>/docs/static/resources/openapi.json \
  -o /tmp/openapi.json
python bin/scripts/extrair_openapi.py /tmp/openapi.json <version> \
  > tests/fixtures/superset_openapi_<version>.json
# point SPEC in tests/unit/test_conformidade_openapi.py to the new file, run the tests and
# fix the reported divergences (POST_FIELDS/PUT_FIELDS, payloads, routes)
```

---

## License

Licensed under the **Mozilla Public License 2.0 (MPL 2.0)**.

---

## Author

Developed and maintained by **COSINF/DIGTI/IFRN**  
Coordenação de Sistemas de Informação  
Diretoria de Gestão da Tecnologia da Informação  
Instituto Federal do Rio Grande do Norte

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **layered MVC service skeleton** (Model–View–Controller) using **native database drivers** (sqlite3, psycopg, mysql-connector-python, pyodbc, oracledb). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Model | `src/model/` | Data access. One service class per file. May touch the DB. Returns pandas DataFrames (or plain dicts/dataclasses). `conexao_db.py` is the connection factory. |
| View | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB imports. |
| Controller | `src/controller/` | Orchestration. Imports model + view + config. `main.py` is the script-style entry-point — top to bottom, no `run()` wrapper. |
| Utils | `src/utils/` | Project-specific helpers. Calendars/parsers/dates come from the `stpstone` dependency, not vendored here. |
| Config | `src/config/` | `startup.py` builds runtime singletons once at import; YAML config files; secrets in `.env`. |

## Key conventions

**`src/controller/main.py` is script-style.** Read top to bottom. It imports the `config.startup` singletons (`LOGGER`, `ENVIRONMENT`, `CLS_MS_TEAMS`, `MSG_MS_TEAMS`, `YAML_*`), inlines its own timer, calls the model, hands the DataFrame to the view, and gates the MS Teams notification behind `ENVIRONMENT == "production"`. Do **not** wrap it in a `run()` function — that is the deliberate MVC convention here.

**`model/conexao_db.build_connection()`** reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — only the configured backend's driver must be installed.

**`model/example_entity.ExampleEntity`** is the reference model: take a connection, run SQL via a cursor, shape rows into a DataFrame with `pd.DataFrame.from_records`. Copy it per entity.

**`view/report_renderer.RenderToExcel`** is the reference view: take a DataFrame, write `.xlsx` via openpyxl, return the path. Add JSON/CSV/HTML renderers alongside it.

**`config/startup.py`** is imported once and builds module-level singletons (logger, MS Teams webhook, log/json paths) from `outputs.yaml` / `webhooks.yaml` / `inputs.yaml` and `.env`. Import it early.

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Adjust the table name, columns, and SQL.
3. Keep all DB access in the model — never in the view or controller.
4. Wire it into `src/controller/main.py`.

## Adding a new DB backend

Add a `_connect_<name>()` helper in `model/conexao_db.py` and register it in the `dict_builders` map inside `build_connection()`.

## Naming conventions

Every variable name starts with a type prefix. No bare names, no underscore prefixes for instances.

| Prefix | Type | Prefix | Type |
|--------|------|--------|------|
| `cls_` | class instance | `list_` | `list` |
| `float_` | `float` | `tuple_` | `tuple` |
| `decimal_` | `Decimal` | `dict_` | `dict` (parsed) |
| `int_` | `int` | `json_` | raw JSON string |
| `str_` | `str` | `df_` | `pd.DataFrame` |
| `bool_` | `bool` (or `is_`/`has_`/`can_`) | `series_` | `pd.Series` |
| `dt_` | `datetime`/`date` | `arr_` | `np.ndarray` |
| `path_` | `pathlib.Path` | `bytes_` | `bytes` |
| `fn_` | `Callable` (standalone vars only — not class methods/attrs) | `re_` | `re.Pattern` |

`json_` = raw unparsed JSON string; `dict_` = already a Python dict.

## File naming conventions

Output files (exports, backups, model artifacts, reports): `name-like-this_YYYYMMDD_HHMMSS.<ext>`
- Name: kebab-case (dashes, no underscores)
- Timestamp: `YYYYMMDD_HHMMSS` (uppercase, sortable)

## Tooling (copied from `templates/python-common/`)

- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, tests, coverage badge.
- **Tests**: `pytest` — `pytest tests/unit/`.
- **Makefile**: `init`, `venv`, `update_venv`, `precommit`, testing, linting, `start`.

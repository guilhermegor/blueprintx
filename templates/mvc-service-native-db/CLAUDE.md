# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **layered MVC service skeleton** (Model–View–Controller) using **native database drivers** (sqlite3, psycopg, mysql-connector-python, pyodbc, oracledb). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Model | `src/model/` | Data access. One service class per file. May touch the DB. Returns pandas DataFrames (or plain dicts/dataclasses). |
| View | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB imports. |
| Controller | `src/controller/` | Orchestration. `main.py` is a thin script-style entry-point that builds `_pipeline.PipelineOrchestrator` and calls `.run()`; the phase sequencing lives in `_pipeline.py`. |
| Utils | `src/utils/` | Helpers. `br_identifiers.py` (CNPJ/CPF mask·unmask·validate) and `dtypes.py` (`apply_dtypes`) are shipped from python-common; calendars/parsers/dates come from the `stpstone` dependency. |
| Config | `src/config/` | `startup.py` builds runtime singletons once at import; `connection_db.py` is the DB connection factory; YAML config files; secrets in `.env`. |

## Library coupling (seams for peripheral dependencies)

Model / View / Controller may use the skeleton's **core data libraries directly** —
`pandas` (the model/view vocabulary) and the configured DB driver via
`config.connection_db`. **Every other third-party dependency** (network, vendor
SDKs, OS-specific APIs, exotic file formats) must be reached through a **seam in
`utils/`** (a gateway/adapter, or a `WebhookNotifier`-style port), so the layer
depends on our function, not the vendor API. This confines breakage from a vendor
change to a single adapter. Example seams shipped here: `utils/webhook/`
(teams/slack behind a port), `utils/paths.py` (OS-independent path resolution).

The **standard library** (`re`, `pathlib`, `datetime`, `json`, …) is unrestricted
in every layer — it carries no coupling risk. Route it through `utils/` only when
the project needs specific behaviour (e.g. `utils/paths.py`), and the reason is the
behaviour, not the import.

## Runtime type-checking (`utils/typing`)

Reach for `from utils.typing import TypeChecker, type_checker` to validate a call's
arguments against their annotations at runtime — `metaclass=TypeChecker` on a class
(or `ProtocolTypeCheckerMeta` for a `Protocol` port), `@type_checker` on a
module-level function. This complements, not replaces, the static gate (ruff `ANN`
+ mypy). The engine caches resolved hints, preserves
`@staticmethod`/`@classmethod`/`property` descriptors, and handles PEP 604 `X | Y`
unions. `utils/typing/` is the one place `Any` is the honest signature (it inspects
values of any type) and is ANN401-exempt. The package ships from
`templates/python-common/optional/typing/` (DDD receives it as `chassis/typing`).
The shared `utils/` helpers (`dtypes`, `br_identifiers`, `decimals`, `loggers`,
`text`, `paths`, `signatures`, `dates`) are intentionally decoupled from it so they
stay portable across tiers — apply the checker in your own model/view/controller
code.

## Key conventions

**`src/controller/main.py` is a thin, script-style entry-point — it defines no functions.** It imports the `config.startup` singletons (`LOGGER`, `ENVIRONMENT`, `APP_NAME`, paths, `output_path`, `YAML_INPUTS`), builds `controller._pipeline.PipelineOrchestrator` with those collaborators injected (the connection factory, `output_path`, the run-context dict, and an `OutlookGateway` e-mail seam), and calls `.run()`. The **phase sequencing lives in `controller/_pipeline.py`** (`PipelineOrchestrator`): `run()` calls `_log_context` → `_open_connection` → `_read` (model) → `_render` (view) → `_write_summary` → `_notify`, each phase bracketed by log lines, the DB connection always closed in a `try/finally`. Business logic stays in the model; the orchestrator only wires and sequences. If the webhook opt-in was chosen at scaffold time, `main.py` injects a production-gated `WebhookNotifier` (`CLS_WEBHOOK` when `ENV` passes the gate, else `None`) plus `MSG_WEBHOOK` into the orchestrator; `run()`'s final `_notify` phase sends it — a no-op when no notifier is wired. The send is part of `run()`, not a tail appended to `main.py`.

**`config/connection_db.build_connection()`** reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — only the configured backend's driver must be installed. SQL Server honours `DB_MSSQL_AUTH` (`sql` for UID/PWD, `aad` for Azure AD Interactive).

**`model/example_entity.ExampleEntity`** is the reference model: take a connection, run SQL via a cursor, shape rows into a DataFrame with `pd.DataFrame.from_records`, then **type every column on load** with `apply_dtypes(df, dict_dtypes=_DICT_DTYPES)` (`utils.dtypes`). Copy it per entity and adjust `_DICT_DTYPES`.

**`view/report_renderer.RenderToExcel`** is the reference view: take a DataFrame, write `.xlsx` via openpyxl, return the path. Add JSON/CSV/HTML renderers alongside it.

**`config/startup.py`** is the **global config copied from `templates/python-common/src/config/`** — do not edit it in this skeleton. It builds the logger and output paths from `outputs.yaml` + `inputs.yaml` and `.env`, and exposes `output_path("<name_key>")` to build any output file path (e.g. the `.xlsx` report). The output directory is data-driven from `inputs.yaml` (`daily_infos_base_path`, default `logs`; optional `daily_infos_dated` date-subfolders). Webhook notifications are **opt-in**: when chosen at scaffold time, a `utils/webhook/` provider plus `CLS_WEBHOOK`/`MSG_WEBHOOK`/`WEBHOOK_ENV_GATE` are wired in (teams/slack via the `WebhookNotifier` port). There is no hardcoded MS Teams webhook and no Brazilian-calendar dependency.

**Explicit column typing & Brazilian identifiers.** Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference (it turns a zero-padded code into an int and a mixed column into `object`). `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`) — the CNPJ helpers are alphanumeric-aware for the 2026 format.

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Adjust the table name, columns, and SQL.
3. Keep all DB access in the model — never in the view or controller.
4. Wire it into `src/controller/main.py`.

## Adding a new DB backend

Add a `_connect_<name>()` helper in `config/connection_db.py` and register it in the `dict_builders` map inside `build_connection()`.

## Data-handling guardrails (advisory)

When a pipeline merges, overrides, or validates tabular data, three recurring traps are
worth guarding against (apply when relevant — these are advisories, not scaffolded code):

- **Override layers must re-apply the canonical normaliser.** A substitution/override path
  that bypasses the same unit/code/sign/default normalisation the primary path uses will
  silently emit inconsistent values. Centralise the invariant in ONE normaliser and call it
  from every path (primary and override alike).
- **Validation rejects sentinel garbage, not just wrong types.** Guard against `"nan"`,
  blank, and out-of-range/wrong-unit values before output — a type check alone passes a
  stringified NaN straight through (see `utils.text.safe_str`).
- **Per-source keyed merge: restrict each partition to the keys it owns before concat.**
  When merging partitions keyed by an id, scope each partition to its own keys first so the
  merge key stays unique and a row from one source never overwrites another's.

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
- **Makefile**: `init`, `venv`, `update_venv`, `precommit`, testing, linting, `run`.

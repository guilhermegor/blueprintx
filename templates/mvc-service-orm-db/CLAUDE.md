# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **layered MVC service skeleton** (Model–View–Controller) using the **SQLAlchemy ORM** (≥2.0). Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MSSQL). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Model | `src/model/` | Data access. ORM models + service classes. May open sessions. Returns pandas DataFrames (or ORM objects). |
| View | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB imports. |
| Controller | `src/controller/` | Orchestration. `main.py` is a thin script-style entry-point that builds `_pipeline.PipelineOrchestrator` and calls `.run()`; the phase sequencing lives in `_pipeline.py`. |
| Utils | `src/utils/` | Helpers. `br_identifiers.py` (CNPJ/CPF mask·unmask·validate) and `dtypes.py` (`apply_dtypes`) are shipped from python-common; calendars/parsers/dates come from the `stpstone` dependency. |
| Config | `src/config/` | `startup.py` builds runtime singletons once at import; `connection_db.py` is the engine/session factory; YAML config files; secrets in `.env`. |

## Library coupling (seams for peripheral dependencies)

Model / View / Controller may use the skeleton's **core data libraries directly** —
`pandas` (the model/view vocabulary) and SQLAlchemy via `config.connection_db`.
**Every other third-party dependency** (network, vendor SDKs, OS-specific APIs,
exotic file formats) must be reached through a **seam in `utils/`** (a
gateway/adapter, or a `WebhookNotifier`-style port), so the layer depends on our
function, not the vendor API. This confines breakage from a vendor change to a
single adapter. Example seams shipped here: `utils/webhook/` (teams/slack behind a
port), `utils/paths.py` (OS-independent path resolution).

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
`text`, `paths`, `signatures`, `dates`, …) carry the runtime checker too — every
function is `@type_checker` and every class uses `metaclass=TypeChecker` (Protocol
ports use `metaclass=ProtocolTypeCheckerMeta`). There is **no by-layer exemption**.
Because those files ship to both tiers, they import the engine through a
layout-agnostic shim — `try: from utils.typing import … except ModuleNotFoundError:
from chassis.typing import …` — so the same source resolves in MVC (`utils.typing`)
and DDD (`chassis.typing`). The only exclusions are the `utils/typing/` engine itself
and classes whose own metaclass would conflict (SQLAlchemy declarative models).

## Key conventions

**`src/controller/main.py` is a thin, script-style entry-point — it defines no functions.** It imports the `config.startup` singletons (`LOGGER`, `ENVIRONMENT`, `APP_NAME`, paths, `output_path`, `YAML_INPUTS`), builds `controller._pipeline.PipelineOrchestrator` with those collaborators injected (the engine factory, `output_path`, the run-context dict, and an `OutlookGateway` e-mail seam), and calls `.run()`. The **phase sequencing lives in `controller/_pipeline.py`** (`PipelineOrchestrator`): `run()` calls `_log_context` → `_open_engine` → `_read` (model) → `_render` (view) → `_write_summary` → `_notify`, each phase bracketed by log lines, the engine always disposed in a `try/finally`. Business logic stays in the model; the orchestrator only wires and sequences. If the webhook opt-in was chosen at scaffold time, `main.py` injects a production-gated `WebhookNotifier` (`CLS_WEBHOOK` when `ENV` passes the gate, else `None`) plus `MSG_WEBHOOK` into the orchestrator; `run()`'s final `_notify` phase sends it — a no-op when no notifier is wired. The send is part of `run()`, not a tail appended to `main.py`. **Multi-intent (opt-in):** if you chose multiple run intents at scaffold time, `main.py` instead dispatches on `PIPELINE_INTENT` via `controller/pipeline_dispatch.build_pipeline`, with one `controller/pipeline_<intent>.py` per purpose (e.g. `send`/`reconcile`) and the shared phases in `controller/pipeline_common.py` — see `src/controller/CLAUDE.md`, which documents both modes and carries the `<!-- pipeline-mode: -->` marker for this project.

**`config/connection_db.build_engine()`** reads `DB_BACKEND` from `.env` and returns a SQLAlchemy `Engine`; `build_session_factory()` returns a bound `sessionmaker`. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. `SQL_ECHO=true` logs SQL. SQL Server honours `DB_MSSQL_AUTH` (`sql` for UID/PWD, `aad` for Azure AD Interactive).

**`model/example_entity`** is the reference model: a `DeclarativeBase`, an ORM-mapped `ExampleRecord`, and an `ExampleEntity` service that opens sessions for writes and uses `pd.read_sql` for reads, then **types every column on load** with `apply_dtypes(df, dict_dtypes=_DICT_DTYPES)` (`utils.dtypes`). Copy it per entity and adjust `_DICT_DTYPES`.

**`view/report_renderer.RenderToExcel`** is the reference view: take a DataFrame, write `.xlsx` via openpyxl, return the path. Add JSON/CSV/HTML renderers alongside it.

**`config/startup.py`** is the **global config copied from `templates/python-common/src/config/`** — do not edit it in this skeleton. It builds the logger and output paths from `outputs.yaml` + `inputs.yaml` and `.env`, and exposes `output_path("<name_key>")` to build any output file path (e.g. the `.xlsx` report). The output directory is data-driven from `inputs.yaml` (`daily_infos_base_path`, default `logs`; optional `daily_infos_dated` date-subfolders). Webhook notifications are **opt-in**: when chosen at scaffold time, a `utils/webhook/` provider plus `CLS_WEBHOOK`/`MSG_WEBHOOK`/`WEBHOOK_ENV_GATE` are wired in (teams/slack via the `WebhookNotifier` port). There is no hardcoded MS Teams webhook and no Brazilian-calendar dependency.

## Session lifecycle rule

The service class owns the `sessionmaker`. Open a session per write and close it in a `finally`; reads use `pd.read_sql` on an engine connection. Keep `commit()` at the service boundary — never inside a lower-level helper.

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Define the ORM-mapped class (inherit from a shared `Base`) and adjust columns.
3. Keep all DB access in the model — never in the view or controller.
4. Wire it into `src/controller/main.py`.

## Adding a new DB backend

Add the SQLAlchemy scheme to `dict_schemes` in `config/connection_db.py` and register the backend key in `dict_builders` inside `build_database_url()`.

## Explicit column typing & Brazilian identifiers

Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference. `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`); the CNPJ helpers are alphanumeric-aware for the 2026 format.

## Data-handling guardrails (advisory)

When a pipeline merges, overrides, or validates tabular data, five recurring traps are
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
- **A time-scoped override input carries a required reference-month and is filtered to the
  run's competency.** A "backdoor" file that forces records into a *specific* run must declare
  a reference-month column (make it contract-required, so a file lacking it is reproved at the
  controller boundary — notify, skip the override, don't abort the run) and be filtered to the
  current month in the model (accept `06/2026` / `2026-06` / `202606` / a datetime cell; log the
  dropped count). Otherwise last period's rows silently re-apply to the wrong target.
- **Canonicalise a join key through the SAME helper on BOTH sides, at the read boundary.**
  When matching frames on a human/regulatory id (CNPJ/CPF/code), normalise the key with one
  canonical helper (e.g. `utils.br_identifiers.unmask_cnpj`) as each frame enters memory —
  never compare a `.map(unmask_*)` series against a bare `.astype(str)` one. A lossy store
  (Excel coercing a 14-digit string to a number, a sqlite TEXT round-trip) drops a leading
  zero, so one side keys on 13 digits and the other on 14 → the join misses *exactly* the
  leading-zero rows, silently (no error, just no match — an approved override dropped).
  Canonicalise on read (healing the persisted store too) and build a normalised key for both
  operands of every merge/overlay.

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

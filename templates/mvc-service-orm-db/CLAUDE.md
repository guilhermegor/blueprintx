# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Engineering principles

See @PRINCIPLES.md for the single-responsibility and function-design rules this project follows.

## Shared conventions

The boundary rules, data-handling guardrails, runtime type-checking notes, naming and
file-naming conventions, tooling summary and the project-memory rule are shared by every
BlueprintX skeleton and live in `.claude/CLAUDE.md` (loaded alongside this file; single
source: `templates/common/CLAUDE.md`). This file keeps only what is specific to this skeleton.

## What this template is

A **layered MVC service skeleton** (Model–View–Controller) using the **SQLAlchemy ORM** (≥2.0). Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MSSQL). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Model | `src/model/` | Data access. ORM models + service classes. May open sessions. Returns pandas DataFrames (or ORM objects). |
| View | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB imports. |
| Controller | `src/controller/` | Orchestration. `main.py` is a thin script-style entry-point that builds `_pipeline.PipelineOrchestrator` and calls `.run()`; the phase sequencing lives in `_pipeline.py`. |
| Utils | `src/utils/` | Helpers. `br_identifiers.py` (CNPJ/CPF mask·unmask·validate) and `dtypes.py` (`apply_dtypes`) are shipped from python-common; the BR calendar comes from the `wwdates` dependency (wrapped by `utils.dates`). |
| Config | `src/config/` | `startup.py` builds runtime singletons once at import; `connection_db.py` is the engine/session factory; YAML config files; secrets in `.env`. |

## Library coupling (seams for peripheral dependencies)

`pandas` is the **vocabulary** Model / View / Controller speak, not an API they call.
`pd.DataFrame` may appear as a parameter or return **annotation** anywhere, but the pandas
*surface* — constructing a frame, reading one — lives behind a seam in `utils/`
(`utils.tabular_reader`, `utils.frames`). SQLAlchemy reaches the layers via
`config.connection_db`; in `model/` it is allowed for the **declaration** of an entity, since
in a declarative mapping the entity *is* its `DeclarativeBase` / `Mapped` / `mapped_column`.

**Every other third-party dependency** (network, vendor SDKs, OS-specific APIs,
exotic file formats) must be reached through a **seam in `utils/`** (a
gateway/adapter, or a `WebhookNotifier`-style port), so the layer depends on our
function, not the vendor API. This confines breakage from a vendor change to a
single adapter. Example seams shipped here: `utils/webhook/` (teams/slack behind a
port), `utils/paths.py` (OS-independent path resolution).

**This is enforced, not advised.** `.layer-policy.yaml` at the project root declares, per
layer, which third-party modules are allowed and why; `bin/check_layer_imports.py` reads it in
pre-commit and CI. Two things worth knowing before you try to work around it:

- **Deferring an import into a function changes nothing.** The gate judges every scope alike —
  the layer still knows the vendor, so hiding the import inside a method is not an exemption
  (the message says so explicitly). The optional-dependency pattern
  (`try: import x / except ImportError: degrade`) is legitimate, but it belongs in the `utils/`
  seam that *owns* the optional dependency and returns the degraded result.
- **Adding an entry to `allow` requires writing the reason.** An allowlist entry without one is
  a rule the next person widens. If the reason is hard to write, the seam is the answer.

The **standard library** (`re`, `pathlib`, `datetime`, `json`, …) is unrestricted
in every layer — it carries no coupling risk. Route it through `utils/` only when
the project needs specific behaviour (e.g. `utils/paths.py`), and the reason is the
behaviour, not the import.

## Key conventions

**`src/controller/main.py` is a thin, script-style entry-point — it defines no functions.** It imports the `config.startup` singletons (`LOGGER`, `ENVIRONMENT`, `APP_NAME`, paths, `output_path`, `YAML_INPUTS`), builds `controller._pipeline.PipelineOrchestrator` with those collaborators injected (the engine factory, `output_path`, the run-context dict, and an `OutlookGateway` e-mail seam), and calls `.run()`. The **phase sequencing lives in `controller/_pipeline.py`** (`PipelineOrchestrator`): `run()` calls `_log_context` → `_open_engine` → `_read` (model) → `_render` (view) → `_write_summary` → `_notify`, each phase bracketed by log lines, the engine always disposed in a `try/finally`. Business logic stays in the model; the orchestrator only wires and sequences. If the webhook opt-in was chosen at scaffold time, `main.py` injects a production-gated `WebhookNotifier` (`CLS_WEBHOOK` when `ENV` passes the gate, else `None`) plus `MSG_WEBHOOK` into the orchestrator; `run()`'s final `_notify` phase sends it — a no-op when no notifier is wired. The send is part of `run()`, not a tail appended to `main.py`. **Multi-intent (opt-in):** if you chose multiple run intents at scaffold time, `main.py` instead dispatches on `PIPELINE_INTENT` via `controller/pipeline_dispatch.build_pipeline`, with one `controller/pipeline_<intent>.py` per purpose (e.g. `send`/`reconcile`) and the shared phases in `controller/pipeline_common.py` — see `src/controller/CLAUDE.md`, which documents both modes and carries the `<!-- pipeline-mode: -->` marker for this project.

**`config/connection_db.build_engine()`** reads `DB_BACKEND` from `.env` and returns a SQLAlchemy `Engine`; `build_session_factory()` returns a bound `sessionmaker`. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. `SQL_ECHO=true` logs SQL. SQL Server honours `DB_MSSQL_AUTH` (`sql` for UID/PWD, `aad` for Azure AD Interactive).

**`model/example_entity`** is the reference model: a `DeclarativeBase`, an ORM-mapped `ExampleRecord`, and an `ExampleEntity` service that opens sessions for writes and **reads through the session** (`session.scalars(select(...))`), projecting each mapped object into a plain mapping and handing those to `utils.frames.from_records`, which **types every column on load**. Copy it per entity and adjust `_DICT_DTYPES`. Note it never calls the pandas API — `pd.DataFrame` is only the return annotation, so copying it propagates the boundary rather than a vendor call.

**`view/report_renderer.RenderToExcel`** is the reference view: take a DataFrame, write `.xlsx` via openpyxl, return the path. Add JSON/CSV/HTML renderers alongside it.

**`config/startup.py`** is the **global config copied from `templates/python-common/src/config/`** — do not edit it in this skeleton. It builds the logger and output paths from `outputs.yaml` + `inputs.yaml` and `.env`, and exposes `output_path("<name_key>")` to build any output file path (e.g. the `.xlsx` report). The output directory is data-driven from `inputs.yaml` (`daily_infos_base_path`, default `logs`; optional `daily_infos_dated` date-subfolders). Webhook notifications are **opt-in**: when chosen at scaffold time, a `utils/webhook/` provider plus `CLS_WEBHOOK`/`MSG_WEBHOOK`/`WEBHOOK_ENV_GATE` are wired in (teams/slack via the `WebhookNotifier` port). There is no hardcoded MS Teams webhook and no Brazilian-calendar dependency.

## Session lifecycle rule

The service class owns the `sessionmaker`. Open a session per write **and per read**, and close it in a `finally`. Keep `commit()` at the service boundary — never inside a lower-level helper.

Reads go through the session (`session.scalars(select(...))`), not `pd.read_sql`: the bare pandas readers are banned project-wide so every read funnels through a seam that enforces types, and the frame is built by `utils.frames.from_records`. Materialise the rows **before** closing the session — a lazily-loaded attribute touched after `close()` raises `DetachedInstanceError`.

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Define the ORM-mapped class (inherit from a shared `Base`) and adjust columns.
3. Keep all DB access in the model — never in the view or controller.
4. Wire it into `src/controller/main.py`.

## Adding a new DB backend

Add the SQLAlchemy scheme to `dict_schemes` in `config/connection_db.py` and register the backend key in `dict_builders` inside `build_database_url()`.

## Explicit column typing & Brazilian identifiers

Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference. `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`); the CNPJ helpers are alphanumeric-aware for the 2026 format.

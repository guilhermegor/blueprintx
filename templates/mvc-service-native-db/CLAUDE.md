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

A **layered MVC service skeleton** (Model–View–Controller) using **native database drivers** (sqlite3, psycopg, mysql-connector-python, pyodbc, oracledb). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Model | `src/model/` | Data access. One service class per file. May touch the DB. Returns pandas DataFrames (or plain dicts/dataclasses). |
| View | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB imports. |
| Controller | `src/controller/` | Orchestration. `main.py` is a thin script-style entry-point that builds `_pipeline.PipelineOrchestrator` and calls `.run()`; the phase sequencing lives in `_pipeline.py`. |
| Utils | `src/utils/` | Helpers. `br_identifiers.py` (CNPJ/CPF mask·unmask·validate) and `dtypes.py` (`apply_dtypes`) are shipped from python-common; the BR calendar comes from the `wwdates` dependency (wrapped by `utils.dates`). |
| Config | `src/config/` | `startup.py` builds runtime singletons once at import; `connection_db.py` is the DB connection factory; YAML config files; secrets in `.env`. |

## Library coupling (seams for peripheral dependencies)

`pandas` is the **vocabulary** Model / View / Controller speak, not an API they call.
Concretely: `pd.DataFrame` may appear as a parameter or return **annotation** anywhere, but
the pandas *surface* — constructing a frame, reading one, reshaping one — lives behind a
seam in `utils/`. Reads go through `utils.tabular_reader` (`read_table` / `read_query`, which
enforce a `FileContract` + dtypes); a frame built from a DB-API cursor goes through
`utils.frames.from_cursor`. The DB driver itself is reached via `config.connection_db`.

The distinction is what keeps a copied file honest: a reference model that *calls* pandas
propagates that call into every entity derived from it, and the layer's dependency on the
vendor grows one copy at a time. An annotation propagates nothing.

**Every other third-party dependency** (network, vendor SDKs, OS-specific APIs,
exotic file formats) must be reached through a **seam in `utils/`** (a
gateway/adapter, or a `WebhookNotifier`-style port), so the layer
depends on our function, not the vendor API.

**This is enforced, not advised.** `.layer-policy.yaml` at the project root declares, per
layer, which third-party modules are allowed and why; `bin/check_layer_imports.py` reads it in
pre-commit and CI. Two things worth knowing before you try to work around it:

- **Deferring an import into a function changes nothing.** The gate judges every scope alike —
  the layer still knows the vendor, so hiding the import inside a method is not an exemption
  (the message says so explicitly). The optional-dependency pattern
  (`try: import x / except ImportError: degrade`) is legitimate, but it belongs in the `utils/`
  seam that *owns* the optional dependency and returns the degraded result.
- **Adding an entry to `allow` requires writing the reason.** An allowlist entry without one is
  a rule the next person widens. If the reason is hard to write, the seam is the answer. This confines breakage from a vendor
change to a single adapter. Example seams shipped here: `utils/webhook/`
(teams/slack behind a port), `utils/paths.py` (OS-independent path resolution).

The **standard library** (`re`, `pathlib`, `datetime`, `json`, …) is unrestricted
in every layer — it carries no coupling risk. Route it through `utils/` only when
the project needs specific behaviour (e.g. `utils/paths.py`), and the reason is the
behaviour, not the import.

## Key conventions

**`src/controller/main.py` is a thin, script-style entry-point — it defines no functions.** It imports the `config.startup` singletons (`LOGGER`, `ENVIRONMENT`, `APP_NAME`, paths, `output_path`, `YAML_INPUTS`), builds `controller._pipeline.PipelineOrchestrator` with those collaborators injected (the connection factory, `output_path`, the run-context dict, and an `OutlookGateway` e-mail seam), and calls `.run()`. The **phase sequencing lives in `controller/_pipeline.py`** (`PipelineOrchestrator`): `run()` calls `_log_context` → `_open_connection` → `_read` (model) → `_render` (view) → `_write_summary` → `_notify`, each phase bracketed by log lines, the DB connection always closed in a `try/finally`. Business logic stays in the model; the orchestrator only wires and sequences. If the webhook opt-in was chosen at scaffold time, `main.py` injects a production-gated `WebhookNotifier` (`CLS_WEBHOOK` when `ENV` passes the gate, else `None`) plus `MSG_WEBHOOK` into the orchestrator; `run()`'s final `_notify` phase sends it — a no-op when no notifier is wired. The send is part of `run()`, not a tail appended to `main.py`. **Multi-intent (opt-in):** if you chose multiple run intents at scaffold time, `main.py` instead dispatches on `PIPELINE_INTENT` via `controller/pipeline_dispatch.build_pipeline`, with one `controller/pipeline_<intent>.py` per purpose (e.g. `send`/`reconcile`) and the shared phases in `controller/pipeline_common.py` — see `src/controller/CLAUDE.md`, which documents both modes and carries the `<!-- pipeline-mode: -->` marker for this project.

**`config/connection_db.build_connection()`** reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — only the configured backend's driver must be installed. SQL Server honours `DB_MSSQL_AUTH` (`sql` for UID/PWD, `aad` for Azure AD Interactive).

**`model/example_entity.ExampleEntity`** is the reference model: take a connection, run SQL via a cursor, and hand the cursor to `utils.frames.from_cursor(cls_cursor, _DICT_DTYPES)`, which shapes the rows and **types every column on load**. Copy it per entity and adjust `_DICT_DTYPES`. Note that it never calls the pandas API — `pd.DataFrame` appears only as the return annotation, so copying it propagates the boundary instead of a vendor call.

**`view/report_renderer.RenderToExcel`** is the reference view: take a DataFrame, write `.xlsx` via openpyxl, return the path. Add JSON/CSV/HTML renderers alongside it.

**`config/startup.py`** is the **global config copied from `templates/python-common/src/config/`** — do not edit it in this skeleton. It builds the logger and output paths from `outputs.yaml` + `inputs.yaml` and `.env`, and exposes `output_path("<name_key>")` to build any output file path (e.g. the `.xlsx` report). The output directory is data-driven from `inputs.yaml` (`daily_infos_base_path`, default `logs`; optional `daily_infos_dated` date-subfolders). Webhook notifications are **opt-in**: when chosen at scaffold time, a `utils/webhook/` provider plus `CLS_WEBHOOK`/`MSG_WEBHOOK`/`WEBHOOK_ENV_GATE` are wired in (teams/slack via the `WebhookNotifier` port). There is no hardcoded MS Teams webhook and no Brazilian-calendar dependency.

**Explicit column typing & Brazilian identifiers.** Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference (it turns a zero-padded code into an int and a mixed column into `object`). `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`) — the CNPJ helpers are alphanumeric-aware for the 2026 format.

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Adjust the table name, columns, and SQL.
3. Keep all DB access in the model — never in the view or controller.
4. Wire it into `src/controller/main.py`.

## Adding a new DB backend

Add a `_connect_<name>()` helper in `config/connection_db.py` and register it in the module-level `_DICT_BUILDERS` map (it sits *below* the `_connect_*` functions because it is evaluated at import — that placement is deliberate). Then create `src/config/queries/<name>/` with a one-line `.sqlfluff` declaring the sqlfluff dialect. No change to `bin/lint_sql.sh` is needed.

## SQL queries — the engine is a directory, not a filename prefix

Queries live at `src/config/queries/<engine>/<table>__<purpose>.sql`, and `config/query_loader.load_query("<table>__<purpose>.sql")` resolves the directory from `DB_BACKEND` via `connection_db.active_backend()` — the single reader of that variable. **Never spell the engine in the filename** and never pass a path: the loader refuses a name carrying a directory, because doing so would route around the one check it exists to make.

Why it is shaped this way: `DB_BACKEND` lives in a git-ignored `.env`, so a repository-only check cannot validate the backend a local or deployed environment actually selects — the file is never committed, and CI never has one. Deriving the directory from the config makes a filename-encoded engine mismatch **unreachable** instead of merely rejected, which beats any check. When a query is genuinely missing, the error names the engines whose directory *does* hold it, so a typo and a misconfiguration do not read identically.

⚠️ **What this does not do:** the layout removes mismatches encoded in a *filename*. It cannot make a wrong `DB_BACKEND` right — that value selects the driver and the SQL together, so an incorrect one simply routes consistently to the wrong engine. `active_backend()` rejects a value that names no supported engine; it cannot know which supported engine you meant.

The directory names the **engine**, not the database instance — two SQL Server databases share one `mssql/`. Each `.sql` opens with a `database / table(s) / purpose` header comment.

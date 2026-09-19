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

## Three boundary rules, each with the test that applies it

The section above says WHERE a boundary goes. These three say when one is worth drawing at
all, and each is stated as a **test you can run on a decision** rather than as advice. All
three cost real rework in a proving ground before they were written down.

### 1. The seam knows the vendor; the callers do not

The rule that keeps a dependency swappable is usually mis-stated as *"hide the library"*, and
the naive reading of that does real damage: annotating the boundary with `Any`, erasing the
vendor's type, protects nobody. It removes the type checking and leaves the coupling exactly
where it was.

What actually makes a vendor swappable is narrower: **the seam imports and TYPES the vendor;
the callers import the seam.**

```python
# utils/http_downloader.py — the seam. It names the vendor, and it types it.
import requests

def download_file(str_url: str, path_dest: Path) -> Path: ...

# model/whatever.py — the caller. It names the SEAM, and nothing else.
from utils.http_downloader import download_file
```

> **The test.** On the day the vendor is replaced, how many files change?
> One (the seam) means the boundary held. More than one means it never existed, however much
> the calling code avoided saying the vendor's name.

This is why `pandas` is `annotation_only` rather than banned outright: `-> pd.DataFrame` in a
signature survives no swap and blocks none — it is the vocabulary the layers agreed on.
`pd.read_sql(...)` is a call, and every file copied from the one that makes it inherits it.

### 2. Externalise text only when the destination has a DIFFERENT change cost

"Take the hard-coded text out of the code and put it in a YAML" reads as separation of
concerns and often is not. The question is never *whether the thing is text*. It is whether
the destination file **changes at a different rate, and by different people.**

A tracked YAML that only the author of the calling code ever edits has separated nothing: it
doubled the number of files that must change together, and added a parse step and a schema to
keep in sync.

> **The test.** Name the person who edits the new file WITHOUT touching the code, and name the
> occasion. If you cannot name both, the text belongs where it is used.
>
> Passes: an e-mail template an operations lead rewords at quarter end. Passes: a locale file
> a translator owns. Fails: a dict of column labels only the developer of that reader will
> ever change.

Measured on a 1,672-line e-mail-body module in a proving ground (2026-08-14), where the
externalised copy was edited exclusively alongside the code that read it.

### 3. Derive the boundary from the config that exists; never restate it

A bootstrap or preflight phase that needs to know *which file belongs to which category*
should **derive** that from the configuration already declaring it, rather than repeating the
list. The duplicate looks harmless the day it is written, because the two copies are identical
then. It is noticed only when they differ — and by then the question is which one is right.

```python
# Avoid — a second list that agrees with the first, until it does not.
LIST_REQUIRED = ["cad_fi.csv", "inf_diario.csv"]

# Prefer — the one declaration is the source; membership is derived from it.
LIST_REQUIRED = [cls_contract.str_filename for cls_contract in contracts.ALL]
```

> **The test.** Could the two copies disagree, and would anything fail if they did?
> If they can disagree silently, one of them must be computed from the other. This is the same
> rule `check_codespell_sync.sh` exists to enforce for the two `.codespellrc` files — that
> pair drifted in both directions, and the stale copy was the one shipping to projects.

## Runtime type-checking (`utils/typing`)

Reach for `from utils.typing import TypeChecker, type_checker` to validate a call's
arguments against their annotations at runtime — `metaclass=TypeChecker` on a class
(or `ProtocolTypeCheckerMeta` for a `Protocol` port), `@type_checker` on a
module-level function. This complements, not replaces, the static gate (ruff `ANN`
+ mypy). The engine is **backed by `beartype`** (`validate.py` is a thin adapter over
it, not a hand-rolled checker — do not reimplement it). Two policies via `BeartypeConf`:
violations raise `TypeError` (beartype's own exception is not a `TypeError` subclass),
and `bool` is **not** accepted where `int` is annotated. These decisions are **knobs in
`utils/typing/policy.py`** (the editable policy seam) — flip one there, never in `validate.py`;
⚠️ `VIOLATION_TYPE` is **load-bearing** (keep it `TypeError`, or downstream `pytest.raises(TypeError)`
breaks). Test note: a bare `Mock` fails a
typed parameter — use `Mock(spec=...)`; and container checks are **sampled O(1)** (one
element per call), not exhaustive. `utils/typing/` is the one place `Any` is the honest signature (it inspects
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

## Data-handling guardrails (advisory)

When a pipeline merges, overrides, or validates tabular data, these recurring traps are
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
- **A filter that REMOVES rows from a deliverable needs a kill switch, not a constant**
  (blueprintx#161). Measured incident: a hard-coded exclusion silently dropped whole fund
  classes from a regulatory delivery; a counterparty had to ask for the missing fund before
  anyone noticed. Sub-delivering costs money per record per day, over-delivering costs
  nothing — so the rule ships as an env-var kill switch with a SAFE-side default (an unset
  *or mistyped* value both resolve to "do not exclude"), and the filter call always returns
  the measured price (rows before/after/dropped), never only the filtered frame. Runnable
  reference: `src/model/scope_filter_example.py` (full rationale in that leaf's `CLAUDE.md`);
  `.env.example` shows the variable.

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

- **Ruff**: linter + formatter. Line-length 99, 4-space indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, tests, coverage badge.
- **Tests**: `pytest` — `pytest tests/unit/`.
- **Makefile**: `init`, `venv`, `update_venv`, `precommit`, testing, linting, `run`.

## Project memory — thin root, lazy leaves (never `@`-imports)

This `CLAUDE.md` is a **thin index**: keep it scannable (what the project is, its structure, the
few commands that matter, the non-negotiable rules) and push domain detail into **leaf**
`CLAUDE.md` files that load **lazily** — a nested `CLAUDE.md` loads on directory entry; a
`rules/*.md` with `paths:` frontmatter loads on file touch. This template already ships leaves
(`src/*/CLAUDE.md`, `docs/CLAUDE.md`, `tests/CLAUDE.md`, `_internal/*/CLAUDE.md`, …).

**Never** wire those leaves through a `@.claude/<topic>.md` table. `@path` is an **eager import** —
Claude Code inlines every referenced file at session start, so a "Documentation" table of `@`-refs
loads *all* of them on *every* session: the structure looks lazy and behaves eager. Nested
`CLAUDE.md` and `paths:`-scoped rules are the only mechanisms that actually defer the load.

Corollary: a prose rule here cannot guard what `settings.json` / hooks auto-approve — put hard
guardrails in permissions or hooks, and keep `CLAUDE.md` for what config cannot express.

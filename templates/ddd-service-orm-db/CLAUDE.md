# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **DDD / hexagonal-architecture service skeleton** using **SQLAlchemy ORM** (≥2.0). Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MSSQL). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

**Scaffold-injected vs authored.** Some code is *not* authored in this skeleton dir — it is injected by the scaffold so it stays a single source of truth:
- `src/config/{startup.py,inputs.yaml,outputs.yaml}` — the **global config** copied from `templates/python-common/src/config/`. Edit it there, not here.
- `src/chassis/db_wschema/` (plus its `chassis/db/` dependency) — **opt-in** schema-less storage (the "schema-less file storage?" prompt). This ORM skeleton's own `db_schema` does not use `chassis/db`, so both are injected together only when storage is chosen. Source in `templates/python-common/optional/chassis/`.
- `src/chassis/webhook/` — **opt-in** (the webhook prompt); a port-based provider from `templates/python-common/optional/webhook/`.
- `src/chassis/typing/` — **always injected**: the runtime type-checking engine (`TypeChecker`, `ProtocolTypeCheckerMeta`, `@type_checker`); source in `templates/python-common/optional/typing/`. **Backed by `beartype`** (`validate.py` is a thin adapter — do not reimplement it): violations raise `TypeError`, `bool` is not accepted as `int`, mocks must be `spec=`-ed, and container checks are sampled O(1). The tunable policy lives in **`chassis/typing/policy.py`** (edit the knobs there, not the adapter; ⚠️ keep `VIOLATION_TYPE` = `TypeError` — it is load-bearing). (The MVC tiers receive the same engine as `utils/typing`.)

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Domain | `src/capabilities/<feature>/domain/` | Pure Python only. No I/O, no ORM imports. `entities.py` (DB shape), `dto.py` (network shape), `enums.py` (types), `ports.py` (Protocols). |
| Application | `src/capabilities/<feature>/application/` | Depends on domain interfaces only. |
| Infrastructure | `src/capabilities/<feature>/infrastructure/` | Implements domain ports using `Session`-backed repositories. |
| Chassis infra | `src/chassis/db_schema/infrastructure/` | `Base`, `DatabaseSession`, `Repository` ABC, `SQLAlchemyRecordRepository`, ORM models. |
| Chassis application | `src/chassis/db_schema/application/` | `build_database_session()` factory — reads `DB_BACKEND` env. |

## Domain file conventions

Each capability domain uses four files with distinct responsibilities:

| File | Purpose | Example |
|------|---------|---------|
| `entities.py` | Persistence shape — maps to a DB row. Has `id`, timestamps, status. | `Note` dataclass |
| `dto.py` | Network shape — what goes over the wire. Inbound (no `id`) and outbound. | `NoteCreateDTO`, `NoteResponseDTO` |
| `enums.py` | Domain-typed constants used by entities and DTOs. | `NoteStatus` |
| `ports.py` | `Protocol` interfaces the infrastructure must satisfy. No inheritance required. | `NoteRepository` |

**`ports.py` uses `Protocol`, not `ABC`** — infrastructure adapters satisfy the contract structurally (duck typing) without importing or inheriting from the domain. This maximises hexagonal decoupling and lets `MagicMock` satisfy ports in tests without any setup.

## Key abstractions

**`Base`** (`src/chassis/db_schema/infrastructure/base.py`):  
`DeclarativeBase` subclass. All ORM models inherit from it. `DatabaseSession.create_tables()` / `drop_tables()` operate on `Base.metadata`.

**`DatabaseSession`** (`src/chassis/db_schema/infrastructure/base.py`):  
Session manager. Use `.session()` for explicit context or `.get_session()` (generator) for FastAPI `Depends` injection.

**`Repository` ABC** (`src/chassis/db_schema/infrastructure/base.py`):  
Abstract CRUD contract (`add / get / update / delete / list_all`). Uses `ABC` (not `Protocol`) because shared session-handling logic lives in the base. Feature repositories extend it and receive a `Session` via constructor (DI — never call `DatabaseSession` directly inside a repository).

**`SQLAlchemyRecordRepository`** (`src/chassis/db_schema/infrastructure/repository.py`):  
Generic implementation that stores any dict as a JSON blob in `RecordModel`. Serves as the reference implementation to copy and adapt per feature.

**`RecordModel`** (`src/chassis/db_schema/infrastructure/models.py`):  
The included ORM model. Define feature-specific models by inheriting from `Base` in `src/chassis/db_schema/infrastructure/models.py` (or a feature-local models file imported into it).

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Add `enums.py` for domain types, `entities.py` for the persistence model, `dto.py` for API shapes, `ports.py` for `Protocol` interfaces.
3. Write use-cases in `application/use_cases.py` — accept port Protocols as constructor args (DI).
4. Add a feature-specific ORM model to `src/chassis/db_schema/infrastructure/models.py`.
5. Implement the domain port in `infrastructure/repositories.py` extending `Repository`; accept a `Session` in `__init__`.
6. Wire in `main.py`: create a `DatabaseSession`, call `create_tables()`, pass sessions into repos.
7. One class per file. No framework or SQLAlchemy imports in `domain/` or `application/`.

## Adding a new chassis provider

Create a new subfolder under `src/chassis/` (e.g. `queues/`, `cache/`) following the same DDD layout:
`domain/`, `application/`, `infrastructure/`. Each provider is self-contained and exposes a clean interface consumed by capabilities.

## Session lifecycle rule

Always **commit outside** the repository: use-cases call `session.commit()` after the repo method returns, or the caller controls the transaction. Repositories call `session.flush()` to assign IDs without committing. Never call `session.commit()` inside a repository method.

## Explicit column typing & Brazilian identifiers

Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference (it turns a zero-padded code into an int and a mixed column into `object`). `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`); the CNPJ helpers are alphanumeric-aware for the 2026 format. These plus `utils.decimals` (`to_decimal`, ROUND_DOWN default), `utils.logs` (`log_message`), `utils.text` (`normalize_text`), `utils.paths` (`is_windows_path`/`resolve_path`/`ensure_dir`), `utils.signatures`, and `utils.dates` (ANBIMA business-day helpers) all ship from `templates/python-common/src/utils/`. The BR calendar also comes from the `stpstone` dependency (wrapped by `utils.dates`).

## Data-handling guardrails (advisory)

When a capability merges, overrides, or validates tabular data, three recurring traps are
worth guarding against (apply when relevant — these are advisories, not scaffolded code):

- **Override layers must re-apply the canonical normaliser.** A substitution/override path
  that bypasses the same unit/code/sign/default normalisation the primary path uses will
  silently emit inconsistent values. Centralise the invariant in ONE normaliser (a domain
  value object is a natural home) and call it from every path.
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
- Exception — joblib artifacts: `name-like-this_YYYYMMDD_HHMMSS_{sha256_prefix8}.joblib`

## Tooling (copied from `templates/python-common/`)

- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests**: `pytest` — `make unit_tests` (`poetry run pytest tests/unit/`). Write pytest-style functions with fixtures, not `unittest.TestCase`.
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

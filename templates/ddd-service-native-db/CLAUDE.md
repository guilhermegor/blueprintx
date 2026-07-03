# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **DDD / hexagonal-architecture service skeleton** using **native database drivers** (psycopg, mysql-connector-python, pyodbc, oracledb, sqlite3). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

**Scaffold-injected vs authored.** Some code is *not* authored in this skeleton dir — it is injected by the scaffold so it stays a single source of truth:
- `src/config/{startup.py,inputs.yaml,outputs.yaml}` — the **global config** copied from `templates/python-common/src/config/`. Edit it there, not here.
- `src/chassis/db/` — always injected (the `DatabaseHandler` ABC that `db_schema` requires); the source lives in `templates/python-common/optional/chassis/db/`.
- `src/chassis/db_wschema/` — **opt-in** (the "schema-less file storage?" prompt). Present only when chosen; source in `templates/python-common/optional/chassis/db_wschema/`. The `STORAGE_BACKEND`/`DATA_DIR`/`JOBLIB_*` `.env` block and the abstractions below appear only then.
- `src/chassis/webhook/` — **opt-in** (the webhook prompt); a port-based provider from `templates/python-common/optional/webhook/`.
- `src/chassis/typing/` — **always injected**: the runtime type-checking engine (`TypeChecker`, `ProtocolTypeCheckerMeta`, `@type_checker`); source in `templates/python-common/optional/typing/`. Preserves `@staticmethod`/`@classmethod`/`property` descriptors and handles PEP 604 `X | Y` unions. (The MVC tiers receive the same engine as `utils/typing`.)

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Domain | `src/capabilities/<feature>/domain/` | Pure Python only. No I/O, no framework imports. `entities.py` (DB shape), `dto.py` (network shape), `enums.py` (types), `ports.py` (Protocols). |
| Application | `src/capabilities/<feature>/application/` | Depends on domain interfaces only. No DB/HTTP libs. |
| Infrastructure | `src/capabilities/<feature>/infrastructure/` | Implements domain ports. Only place for DB/HTTP calls. |
| Chassis infra | `src/chassis/db_schema/infrastructure/` | Shared DB handlers extending `DatabaseHandler` ABC. |
| Chassis application | `src/chassis/db_schema/application/` | `build_database_handler()` factory — reads `DB_BACKEND` env. |
| Chassis domain | `src/chassis/db_schema/domain/` | Shared entities/value objects only if truly cross-cutting. |

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

**`DatabaseHandler` ABC** (`src/chassis/db/domain/ports.py`):  
Shared contract for all storage backends: `create / read / update / delete / backup / close`. Named `ports.py` to signal its role; uses `ABC` (not `Protocol`) for runtime enforcement of complete implementations. `ensure_id` helper lives in `src/chassis/db/infrastructure/helpers.py`.

**Chassis providers:**

| Provider | Location | Backends |
|----------|----------|---------|
| `db` | `chassis/db/` | Shared `DatabaseHandler` ABC + `Record` type + `ensure_id` helper |
| `db_schema` | `chassis/db_schema/` | SQL-backed: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle` |
| `db_wschema` | `chassis/db_wschema/` | Schema-less: `json`, `csv`, `joblib` |

**`build_database_handler()`** (`src/chassis/db_schema/application/database_factory.py`):  
Reads `DB_BACKEND` from `.env`. Supported values: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.

**`build_storage_handler()`** (`src/chassis/db_wschema/application/storage_factory.py`):  
Reads `STORAGE_BACKEND` from `.env`. Supported values: `json`, `csv`, `joblib`.

**`JoblibHandler`** (`src/chassis/db_wschema/infrastructure/joblib_handler.py`):  
Immutable binary artifact store. Each artifact is a file named `{name}_{YYYYMMDD_HHMMSS}_{sha256_prefix8}.joblib`. Three-factor integrity on load: SHA256 prefix in filename, `_saved_at` metadata match, optional HMAC sidecar. `update()` raises `NotImplementedError` — save new artifacts with `create()`.

**`SanityCheck`** (`src/chassis/db_wschema/infrastructure/sanity_check.py`):  
Post-load semantic validator. Pass `expected_class_name` and `required_attrs`; call `.validate(obj)` after loading.

**Port/Repository pattern** (`src/capabilities/example_feature/domain/ports.py`):  
`NoteRepository` is a `Protocol` port. `InMemoryNoteRepository` in `infrastructure/repositories.py` satisfies it without inheritance. Add a real DB-backed implementation there; never in the domain or application layers.

**`src/main.py`**:  
Wires everything together: loads `.env`, calls `build_database_handler()` or `build_storage_handler()`, instantiates repos and use-cases.

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Add `enums.py` for domain types, `entities.py` for the persistence model, `dto.py` for API shapes, `ports.py` for `Protocol` interfaces.
3. Write use-cases in `application/use_cases.py` — accept port Protocols as constructor args (DI).
4. Implement the port in `infrastructure/repositories.py` using a `DatabaseHandler` from `chassis`.
5. Wire in `main.py`.
6. One class per file. No framework code in `application/`.

## Adding a new DB backend

Subclass `DatabaseHandler` in `src/chassis/db_schema/infrastructure/<name>_handler.py`, implement all six abstract methods, export from `src/chassis/db_schema/infrastructure/__init__.py`, and add the key to the `builders` dict in `database_factory.py`.

## Adding a new chassis provider

Create a new subfolder under `src/chassis/` (e.g. `queues/`, `cache/`) following the same DDD layout:
`domain/`, `application/`, `infrastructure/`. Each provider is self-contained and exposes a clean interface consumed by capabilities.

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

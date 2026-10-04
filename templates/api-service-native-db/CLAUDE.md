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

An **HTTP API service skeleton** — hexagonal DDD layers plus a FastAPI **transport** layer — using **native database drivers** (psycopg, mysql-connector-python, pyodbc, oracledb, sqlite3). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project. Named for the ROLE (API service), not the framework: `src/app/api.py` is the one place that imports FastAPI at the composition-root level, so a future framework swap touches one file plus each capability's `transport/routers.py`.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

**Scaffold-injected vs authored.** Some code is *not* authored in this skeleton dir — it is injected by the scaffold so it stays a single source of truth:
- `src/config/{startup.py,inputs.yaml,outputs.yaml}` — the **global config** copied from `templates/python-common/src/config/`. Edit it there, not here.
- `src/chassis/db/` — always injected (the `DatabaseHandler` ABC that `db_schema` requires); the source lives in `templates/python-common/optional/chassis/db/`.
- `src/chassis/db_wschema/` — **opt-in** (the "schema-less file storage?" prompt). Present only when chosen; source in `templates/python-common/optional/chassis/db_wschema/`. The `STORAGE_BACKEND`/`DATA_DIR`/`JOBLIB_*` `.env` block and the abstractions below appear only then.
- `src/chassis/webhook/` — **opt-in** (the webhook prompt); a port-based provider from `templates/python-common/optional/webhook/`.
- `src/chassis/typing/` — **always injected**: the runtime type-checking engine (`TypeChecker`, `ProtocolTypeCheckerMeta`, `@type_checker`); source in `templates/python-common/optional/typing/`. **Backed by `beartype`** (`validate.py` is a thin adapter — do not reimplement it): violations raise `TypeError`, `bool` is not accepted as `int`, mocks must be `spec=`-ed, and container checks are sampled O(1). The tunable policy lives in **`chassis/typing/policy.py`** (edit the knobs there, not the adapter; ⚠️ keep `VIOLATION_TYPE` = `TypeError` — it is load-bearing). (The MVC tiers receive the same engine as `utils/typing`.)

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Domain | `src/capabilities/<feature>/domain/` | Pure Python only. No I/O, no framework imports. `entities.py` (DB shape), `dto.py` (network shape), `enums.py` (types), `ports.py` (Protocols). |
| Application | `src/capabilities/<feature>/application/` | Depends on domain interfaces only. No DB/HTTP libs. |
| Infrastructure | `src/capabilities/<feature>/infrastructure/` | Implements domain ports. Only place for DB/outbound-HTTP calls. |
| Transport | `src/capabilities/<feature>/transport/` | Inbound HTTP adapter (FastAPI `APIRouter`). Takes injected callables, never the container — see `.layer-policy.yaml`. |
| App (composition root) | `src/app/` | `api.py` (ASGI app factory), `container.py` (wiring), `bootstrap.py` (env/logging/teardown). Only place transport and container meet. |
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

**`src/app/api.py`** (`create_app()`):  
Builds the composition root's container, mounts every capability's router, and adds `/health`.
`src/main.py` calls it and hands the result to `uvicorn.run()`.

**`src/main.py`**:  
Bootstrap → wire (`create_app()`) → serve (blocks on `uvicorn.run`) → teardown on shutdown.

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Add `enums.py` for domain types, `entities.py` for the persistence model, `dto.py` for API shapes, `ports.py` for `Protocol` interfaces.
3. Write use-cases in `application/use_cases.py` — accept port Protocols as constructor args (DI).
4. Implement the port in `infrastructure/repositories.py` using a `DatabaseHandler` from `chassis`.
5. If the capability is reachable over HTTP, add `transport/routers.py`: one `build_<feature>_router()` taking plain callables (never the container — see `.layer-policy.yaml`'s `capabilities/*/transport` entry).
6. Wire the container in `app/container.py`, then mount the router in `app/api.py`.
7. One class per file. No framework code in `application/` or `domain/`.

## Adding a new DB backend

Subclass `DatabaseHandler` in `src/chassis/db_schema/infrastructure/<name>_handler.py`, implement all six abstract methods, export from `src/chassis/db_schema/infrastructure/__init__.py`, and add the key to the module-level `_DICT_BUILDERS` map in `database_factory.py` (each builder takes the backend name, so the map lives at module scope and `SET_BACKENDS` derives from it — one source for the engine names). Then create `src/config/queries/<name>/` with a one-line `.sqlfluff` declaring the sqlfluff dialect. No change to `bin/lint_sql.sh` is needed.

## SQL queries — the engine is a directory, not a filename prefix

Queries live at `src/config/queries/<engine>/<table>__<purpose>.sql`, and `config/query_loader.load_query("<table>__<purpose>.sql")` resolves the directory from `DB_BACKEND` via `chassis.db_schema.application.database_factory.active_backend()` — the single reader of that variable. **Never spell the engine in the filename** and never pass a path: the loader refuses a name carrying a directory, because doing so would route around the one check it exists to make.

Why it is shaped this way: `DB_BACKEND` lives in a git-ignored `.env`, so a repository-only check cannot validate the backend a local or deployed environment actually selects — the file is never committed, and CI never has one. Deriving the directory from the config makes a filename-encoded engine mismatch **unreachable** instead of merely rejected, which beats any check. When a query is genuinely missing, the error names the engines whose directory *does* hold it, so a typo and a misconfiguration do not read identically.

⚠️ **What this does not do:** the layout removes mismatches encoded in a *filename*. It cannot make a wrong `DB_BACKEND` right — that value selects the driver and the SQL together, so an incorrect one simply routes consistently to the wrong engine. `active_backend()` rejects a value that names no supported engine; it cannot know which supported engine you meant.

The directory names the **engine**, not the database instance — two SQL Server databases share one `mssql/`. Each `.sql` opens with a `database / table(s) / purpose` header comment.

## Adding a new chassis provider

Create a new subfolder under `src/chassis/` (e.g. `queues/`, `cache/`) following the same DDD layout:
`domain/`, `application/`, `infrastructure/`. Each provider is self-contained and exposes a clean interface consumed by capabilities.

## Explicit column typing & Brazilian identifiers

Every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`utils.dtypes`) — never rely on pandas' inference (it turns a zero-padded code into an int and a mixed column into `object`). `apply_dtypes` also takes optional `list_date_cols` / `list_datetime_cols`. For CNPJ/CPF use `utils.br_identifiers` (`mask_*`, `unmask_*`, `is_valid_*`); the CNPJ helpers are alphanumeric-aware for the 2026 format. These plus `utils.decimals` (`to_decimal`, ROUND_DOWN default), `utils.logs` (`log_message`), `utils.text` (`normalize_text`), `utils.paths` (`is_windows_path`/`resolve_path`/`ensure_dir`), `utils.signatures`, and `utils.dates` (ANBIMA business-day helpers) all ship from `templates/python-common/src/utils/`. The BR calendar comes from the `wwdates` dependency (wrapped by `utils.dates`).

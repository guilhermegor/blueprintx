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
- `src/chassis/typing/` — **always injected**: the runtime type-checking engine (`TypeChecker`, `ProtocolTypeCheckerMeta`, `@type_checker`); source in `templates/python-common/optional/typing/`. **Backed by `beartype`** (`validate.py` is a thin adapter — do not reimplement it): violations raise `TypeError`, `bool` is not accepted as `int`, mocks must be `spec=`-ed, and container checks are sampled O(1). The tunable policy lives in **`chassis/typing/policy.py`** (edit the knobs there, not the adapter; ⚠️ keep `VIOLATION_TYPE` = `TypeError` — it is load-bearing). (The MVC tiers receive the same engine as `utils/typing`.)

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
# chassis/http/http_downloader.py — the seam. It names the vendor, and it types it.
import requests

def download_file(str_url: str, path_dest: Path) -> Path: ...

# capabilities/<feature>/infrastructure/adapter.py — the caller. It names the SEAM only.
from chassis.http.http_downloader import download_file
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

- **Ruff**: linter + formatter. Line-length 99, 4-space indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests**: `pytest` — `poe unit_tests`. Write pytest-style functions with fixtures, not `unittest.TestCase`.
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

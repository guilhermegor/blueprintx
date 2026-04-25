# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **DDD / hexagonal-architecture service skeleton** using **SQLAlchemy ORM** (≥2.0). Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MSSQL). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

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
- **Tests**: `unittest` discovered with `python -m unittest discover -s tests/unit -p "*.py"`.
- **Makefile**: `init`, `venv`, `update-venv`, `precommit`, testing, linting, `start`.

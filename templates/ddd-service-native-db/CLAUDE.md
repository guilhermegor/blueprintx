# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **DDD / hexagonal-architecture service skeleton** using **native database drivers** (psycopg, mysql-connector-python, pyodbc, oracledb, sqlite3). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Domain | `src/modules/<feature>/domain/` | Pure Python only. No I/O, no framework imports. |
| Application | `src/modules/<feature>/application/` | Depends on domain interfaces only. No DB/HTTP libs. |
| Infrastructure | `src/modules/<feature>/infrastructure/` | Implements domain ports. Only place for DB/HTTP calls. |
| Core infra | `src/core/infrastructure/database/` | Shared DB handlers extending `DatabaseHandler` ABC. |
| Core application | `src/core/application/` | `build_database_handler()` factory — reads `DB_BACKEND` env. |
| Core domain | `src/core/domain/` | Shared entities/value objects only if truly cross-cutting. |

## Key abstractions

**`DatabaseHandler` ABC** (`src/core/infrastructure/database/base.py`):  
All DB backends implement `create / read / update / delete / backup / close`. The `ensure_id` helper assigns a UUID hex when no `id` is present.

**`build_database_handler()`** (`src/core/application/database_factory.py`):  
Reads `DB_BACKEND` from `.env` and returns the matching handler. Supported values: `json`, `csv`, `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.

**Port/Repository pattern** (`src/modules/example_feature/domain/ports.py`):  
`NoteRepository` is the ABC port. `InMemoryNoteRepository` in `infrastructure/repositories.py` implements it. Add a real DB-backed implementation there; never in the domain or application layers.

**`src/main.py`**:  
Wires everything together: loads `.env`, calls `build_database_handler()`, instantiates repos and use-cases. The `RUN_DEMO=true` env flag triggers demo execution.

## Adding a new feature module

1. Create `src/modules/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Define entities in `domain/entities.py` and the repository ABC in `domain/ports.py`.
3. Write use-cases in `application/use_cases.py` — accept ports as constructor args (DI).
4. Implement the port in `infrastructure/repositories.py` using a `DatabaseHandler` from `core`.
5. Wire in `main.py`.
6. One class per file. Ports (ABCs) stay in `domain/`; no framework code in `application/`.

## Adding a new DB backend

Subclass `DatabaseHandler` in `src/core/infrastructure/database/<name>_handler.py`, implement all six abstract methods, export from `src/core/infrastructure/database/__init__.py`, and add the key to the `builders` dict in `database_factory.py`.

## Tooling (copied from `templates/python-common/`)

- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests**: `unittest` discovered with `python -m unittest discover -s tests/unit -p "*.py"`.
- **Makefile**: `init-venv`, `update-venv`, `vscode_init`, `export_deps`.

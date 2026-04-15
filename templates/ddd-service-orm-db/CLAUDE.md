# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **DDD / hexagonal-architecture service skeleton** using **SQLAlchemy ORM** (≥2.0). Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MSSQL). It is scaffolded by BlueprintX into a new project directory — the files here are the authoritative template source, not a running project.

The `pyproject.toml` uses `${VARIABLE}` placeholders resolved via `envsubst` at scaffold time. Do not replace them with literal values.

## Layer boundaries (strict — do not cross)

| Layer | Location | Rule |
|-------|----------|------|
| Domain | `src/modules/<feature>/domain/` | Pure Python only. No I/O, no ORM imports. |
| Application | `src/modules/<feature>/application/` | Depends on domain interfaces only. |
| Infrastructure | `src/modules/<feature>/infrastructure/` | Implements domain ports using `Session`-backed repositories. |
| Core infra | `src/core/infrastructure/database/` | `Base`, `DatabaseSession`, `Repository` ABC, `SQLAlchemyRecordRepository`, ORM models. |
| Core application | `src/core/application/` | `build_database_session()` factory — reads `DATABASE_URL` env. |

## Key abstractions

**`Base`** (`src/core/infrastructure/database/base.py`):  
`DeclarativeBase` subclass. All ORM models inherit from it. `DatabaseSession.create_tables()` / `drop_tables()` operate on `Base.metadata`.

**`DatabaseSession`** (`src/core/infrastructure/database/base.py`):  
Session manager. Use `.session()` for explicit context or `.get_session()` (generator) for FastAPI `Depends` injection.

**`Repository` ABC** (`src/core/infrastructure/database/base.py`):  
Abstract CRUD contract (`add / get / update / delete / list_all`). All feature repositories must extend it and receive a `Session` via constructor (DI — never call `DatabaseSession` directly inside a repository).

**`SQLAlchemyRecordRepository`** (`src/core/infrastructure/database/repository.py`):  
Generic implementation that stores any dict as a JSON blob in `RecordModel`. Serves as the reference implementation to copy and adapt per feature.

**`RecordModel`** (`src/core/infrastructure/database/models.py`):  
The included ORM model. Define feature-specific models by inheriting from `Base` in `src/core/infrastructure/database/models.py` (or a feature-local models file imported into it).

## Adding a new feature module

1. Create `src/modules/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Define entities in `domain/entities.py` and the repository ABC in `domain/ports.py`.
3. Write use-cases in `application/use_cases.py` — accept domain port ABCs as constructor args.
4. Add a feature-specific ORM model to `src/core/infrastructure/database/models.py`.
5. Implement the domain port in `infrastructure/repositories.py` extending `Repository`; accept a `Session` in `__init__`.
6. Wire in `main.py`: create a `DatabaseSession`, call `create_tables()`, pass sessions into repos.
7. One class per file. No framework or SQLAlchemy imports in `domain/` or `application/`.

## Session lifecycle rule

Always **commit outside** the repository: use-cases call `session.commit()` after the repo method returns, or the caller controls the transaction. Repositories call `session.flush()` to assign IDs without committing. Never call `session.commit()` inside a repository method.

## Tooling (copied from `templates/python-common/`)

- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings. Config: `ruff.toml`.
- **Pre-commit**: ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests**: `unittest` discovered with `python -m unittest discover -s tests/unit -p "*.py"`.
- **Makefile**: `init-venv`, `update-venv`, `vscode_init`, `export_deps`.

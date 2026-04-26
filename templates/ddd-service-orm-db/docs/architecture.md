# **Architecture — DDD Service (ORM DB)**

A hexagonal (ports-and-adapters) architecture with Domain-Driven Design layers, using **SQLAlchemy ORM** (≥2.0) for database access. Business logic is isolated from I/O — ORM models and sessions are confined to the infrastructure layer.

| Aspect | Native DB | This template (ORM) |
|--------|-----------|---------------------|
| Database access | Direct drivers (psycopg2, sqlite3, etc.) | SQLAlchemy ORM Session |
| Query style | Raw SQL or driver cursor | ORM query API / Core expressions |
| Repository base | `DatabaseHandler` ABC | `Repository` ABC (session-injected) |
| Schema management | Manual DDL / migrations | `Base.metadata.create_all()` / Alembic |

---

## Expected layout

```bash
project/
  src/
    capabilities/<feature>/
      domain/               # entities.py · dto.py · enums.py · ports.py
      application/          # use_cases.py
      infrastructure/       # repositories.py
    chassis/
      db_schema/
        application/database_factory.py   # build_database_session()
        infrastructure/
          base.py           # Base, DatabaseSession, Repository ABC
          models.py         # ORM model definitions (inherit from Base)
          repository.py     # SQLAlchemyRecordRepository (generic reference impl)
    config/
      startup.py            # logger, runtime constants (module-level singletons)
    main.py
  tests/{unit,integration,performance}/
  docs/
  .env
  pyproject.toml
```

---

## Folder descriptions

| Folder | Purpose | Expected content |
|--------|---------|-----------------|
| `src/capabilities/<feature>/` | Feature-specific code | Bounded context with domain, application, and infrastructure sub-layers |
| `src/capabilities/<feature>/domain/` | Pure business logic | `entities.py`, `dto.py`, `enums.py`, `ports.py` — no ORM imports |
| `src/capabilities/<feature>/application/` | Use-case orchestration | `use_cases.py` — no framework or SQLAlchemy imports |
| `src/capabilities/<feature>/infrastructure/` | Adapters implementing ports | `repositories.py` — Session-backed repository implementations |
| `src/chassis/db_schema/` | ORM session management | `DatabaseSession`, `Repository` ABC, ORM models, generic repository |
| `src/config/` | Runtime configuration | `startup.py` for singletons; YAML config files; secrets in `.env` |
| `tests/unit/` | Isolated domain tests | Fast tests with no I/O — mock at infrastructure boundaries |
| `tests/integration/` | Integration tests | Tests using real databases or external services |
| `docs/` | Project documentation | This MkDocs site |

---

## Layers

### Domain (`capabilities/<feature>/domain`)

**What goes here:** Four files with distinct responsibilities — no ORM, no framework, no I/O anywhere in this layer.

```python
# ports.py — Protocol, not ABC: infrastructure satisfies it structurally (no import needed)
from typing import Iterable, Protocol
from .entities import Note

class NoteRepository(Protocol):
    def add(self, cls_note: Note) -> Note: ...
    def get(self, str_note_id: str) -> Note | None: ...
    def list(self) -> Iterable[Note]: ...
```

### Application (`capabilities/<feature>/application`)

**What goes here:** Use-case orchestration. Accepts port Protocols via dependency injection — never imports SQLAlchemy directly.

```python
# use_cases.py
from ..domain.dto import NoteCreateDTO, NoteResponseDTO
from ..domain.entities import Note
from ..domain.ports import NoteRepository

def create_note(cls_dto: NoteCreateDTO, cls_repo: NoteRepository) -> NoteResponseDTO:
    cls_note = Note(title=cls_dto.title)
    cls_stored = cls_repo.add(cls_note)
    return NoteResponseDTO(
        id=cls_stored.id,
        title=cls_stored.title,
        created_at=cls_stored.created_at,
        status=cls_stored.status,
    )
```

### Infrastructure (`capabilities/<feature>/infrastructure`)

**What goes here:** Session-backed repository implementations. Each repository receives a `Session` via constructor — never calls `DatabaseSession` directly.

```python
# repositories.py — extend Repository ABC; receive Session via DI
from sqlalchemy.orm import Session
from chassis.db_schema.infrastructure.base import Repository
from ..domain.entities import Note

class SQLNoteRepository(Repository):
    def __init__(self, cls_session: Session) -> None:
        self._cls_session = cls_session

    def add(self, cls_note: Note) -> Note:
        self._cls_session.add(cls_note)
        self._cls_session.flush()   # assigns id without committing
        return cls_note

    def get(self, str_note_id: str) -> Note | None:
        return self._cls_session.get(Note, str_note_id)

    def list(self) -> list[Note]:
        return self._cls_session.query(Note).all()
```

!!! warning "Session lifecycle rule"
    Repositories call `session.flush()` to assign IDs; use-cases or callers call
    `session.commit()`. Never commit inside a repository method.

### Chassis (`chassis/db_schema/`)

**What goes here:** The ORM session infrastructure — shared by all features.

```python
# main.py — wiring example
from chassis.db_schema.application import build_database_session

# reads DB_BACKEND from .env — e.g. DB_BACKEND=sqlite  DB_URL=sqlite:///./data/app.db
cls_db_session = build_database_session()
cls_db_session.create_tables()   # runs Base.metadata.create_all()

with cls_db_session.session() as cls_session:
    cls_repo = SQLNoteRepository(cls_session)
    cls_note = create_note(NoteCreateDTO(title="Hello"), cls_repo)
    cls_session.commit()
```

For FastAPI `Depends` injection, use `cls_db_session.get_session()` (a generator).

---

## Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no ORM or framework imports |
| **Application** | Orchestrate use-cases and policies; framework-free |
| **Infrastructure** | Session-backed adapters implementing domain ports |
| **Chassis** | `DatabaseSession`, `Repository` ABC, ORM models, generic repository |
| **Config** | Shared runtime constants; secrets stay in `.env` |

---

## Learn more

- [API Reference](api.md) — session factory usage, use-case wiring, and extension patterns

# **API Reference — DDD Service (ORM DB)**

Usage examples for the SQLAlchemy session factory, use-case wiring, and extension patterns.

> **See also:** [Architecture](architecture.md)

---

## Session factory

`build_database_session()` reads `DB_BACKEND` from `.env` and returns a configured `DatabaseSession`.

```python
from chassis.db_schema.application import build_database_session

# .env: DB_BACKEND=sqlite  DB_URL=sqlite:///./data/app.db
cls_db_session = build_database_session()
cls_db_session.create_tables()   # runs Base.metadata.create_all()
```

Supported values for `DB_BACKEND`: `sqlite`, `postgresql`, `mysql`, `mssql`, `oracle`.

---

## Session context manager

Use `.session()` for an explicit context-managed session. The session is committed or rolled back automatically on exit.

```python
with cls_db_session.session() as cls_session:
    cls_repo = SQLNoteRepository(cls_session)
    cls_note = create_note(NoteCreateDTO(title="Hello"), cls_repo)
    cls_session.commit()   # commit happens in the caller, not the repository
```

---

## FastAPI dependency injection

Use `.get_session()` (a generator) with `Depends` for per-request session management.

```python
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

app = FastAPI()

def get_db() -> Session:
    yield from cls_db_session.get_session()

@app.post("/notes")
def create(cls_dto: NoteCreateDTO, cls_session: Session = Depends(get_db)) -> NoteResponseDTO:
    cls_repo = SQLNoteRepository(cls_session)
    cls_note = create_note(cls_dto, cls_repo)
    cls_session.commit()
    return cls_note
```

---

## Wiring a use-case in main.py

```python
from capabilities.notes.domain.dto import NoteCreateDTO
from capabilities.notes.infrastructure.repositories import SQLNoteRepository
from capabilities.notes import use_cases

with cls_db_session.session() as cls_session:
    cls_repo = SQLNoteRepository(cls_session)
    cls_note = use_cases.create_note(NoteCreateDTO(title="Hello"), cls_repo)
    cls_session.commit()
    print(cls_note.id, cls_note.title)
```

---

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Define domain files: `enums.py` (constants), `entities.py` (persistence shape), `dto.py` (network shape), `ports.py` (Protocol interfaces).
3. Add a feature-specific ORM model to `src/chassis/db_schema/infrastructure/models.py` inheriting from `Base`.
4. Write use-cases in `application/use_cases.py` — accept port Protocols as arguments (dependency injection).
5. Implement the port in `infrastructure/repositories.py` extending `Repository`; receive a `Session` in `__init__`.
6. Wire in `main.py`: create a `DatabaseSession`, call `create_tables()`, pass sessions into repos.

One class per file. No SQLAlchemy imports inside `domain/` or `application/`.

---

## Adding a new chassis provider

Create `src/chassis/<provider>/{domain,application,infrastructure}/` following the same DDD sub-layer pattern. Each provider is self-contained and exposes a clean interface consumed by capabilities.

# **DDD Service (ORM) — Usage Examples**

Basic examples demonstrating the DDD hexagonal architecture with SQLAlchemy ORM.

> **See also:** [Core concepts](../ddd-service-orm-db.md) · [External API calls](ddd-orm-external-api.md) · [Bank balance alert](ddd-orm-bank-balance-alert.md)

---

## Minimal end-to-end demo (SQLAlchemy)

A quick example wiring all layers together with SQLAlchemy:

```python
from core.application import build_database_session
from core.infrastructure.database import SQLAlchemyRecordRepository

# Build database session from environment
db = build_database_session()
db.create_tables()

# Use the repository
with db.session() as session:
    repo = SQLAlchemyRecordRepository(session)
    
    # Create a record
    record_id = repo.add({"title": "First note", "content": "Hello world"})
    session.commit()
    
    # List all records
    print(repo.list_all())
```

---

## Using feature capabilities with SQLAlchemy

The feature capabilities work the same way — inject SQLAlchemy-based repositories:

```python
from core.application import build_database_session
from capabilities.example_feature.application.use_cases import CreateNote, ListNotes
from capabilities.example_feature.infrastructure.repositories import InMemoryNoteRepository

# For demos/tests — use in-memory
repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

create_note.execute("First note")
print(list_notes.execute())
```

---

## Wiring with FastAPI + SQLAlchemy

Example composition with FastAPI dependency injection:

```python
# composition.py
from core.application import build_database_session
from core.infrastructure.database import SQLAlchemyRecordRepository

db = build_database_session()
db.create_tables()


def get_record_repo():
    """Dependency that yields a repository per request."""
    with db.session() as session:
        yield SQLAlchemyRecordRepository(session)
```

```python
# api/records.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from .composition import get_record_repo
from core.infrastructure.database import SQLAlchemyRecordRepository

router = APIRouter(prefix="/records", tags=["records"])


class CreateRecordPayload(BaseModel):
    title: str
    content: str


@router.post("/")
def create_record(
    payload: CreateRecordPayload,
    repo: SQLAlchemyRecordRepository = Depends(get_record_repo),
):
    record_id = repo.add({"title": payload.title, "content": payload.content})
    # Note: commit happens when session closes in the dependency
    return {"id": record_id, "title": payload.title}


@router.get("/")
def list_records(repo: SQLAlchemyRecordRepository = Depends(get_record_repo)):
    return repo.list_all()


@router.get("/{record_id}")
def get_record(
    record_id: str,
    repo: SQLAlchemyRecordRepository = Depends(get_record_repo),
):
    record = repo.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
```

---

## Swapping database backends

The power of SQLAlchemy: swap databases by changing `.env` only.

```bash
# .env for SQLite (local dev)
DB_BACKEND=sqlite
SQLITE_PATH=app.db

# .env for PostgreSQL (production)
DB_BACKEND=postgresql
POSTGRES_USER=myuser
POSTGRES_PASSWORD=secret
POSTGRES_HOST=db.example.com
POSTGRES_DB=myapp
```

```python
# Same code works with any backend
from core.application import build_database_session

db = build_database_session()  # Reads DB_BACKEND from .env
db.create_tables()

# Works with SQLite, PostgreSQL, MySQL, Oracle, MSSQL...
with db.session() as session:
    repo = SQLAlchemyRecordRepository(session)
    repo.add({"title": "Works anywhere!"})
    session.commit()
```

---

## Creating custom ORM models

Extend the base to create your own models:

```python
# capabilities/notes/infrastructure/models.py
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from core.infrastructure.database import Base, generate_uuid


class NoteModel(Base):
    """SQLAlchemy model for Note entity."""

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def to_entity(self) -> "Note":
        """Convert ORM model to domain entity."""
        from ..domain.entities import Note
        return Note(id=self.id, title=self.title, content=self.content)
```

---

## Custom repository with SQLAlchemy

```python
# capabilities/notes/infrastructure/repositories.py
from typing import Optional
from sqlalchemy.orm import Session
from core.infrastructure.database import Repository
from .models import NoteModel
from ..domain.entities import Note
from ..domain.ports import NoteRepository


class SQLAlchemyNoteRepository(NoteRepository, Repository):
    """SQLAlchemy implementation of NoteRepository."""

    def __init__(self, session: Session):
        super().__init__(session)

    def add(self, note: Note) -> Note:
        model = NoteModel(id=note.id, title=note.title, content=note.content)
        self.session.add(model)
        self.session.flush()
        return note

    def get(self, note_id: str) -> Optional[Note]:
        model = self.session.get(NoteModel, note_id)
        return model.to_entity() if model else None

    def list_all(self) -> list[Note]:
        models = self.session.query(NoteModel).all()
        return [m.to_entity() for m in models]

    def delete(self, note_id: str) -> bool:
        model = self.session.get(NoteModel, note_id)
        if model:
            self.session.delete(model)
            return True
        return False

    def update(self, note: Note) -> Optional[Note]:
        model = self.session.get(NoteModel, note.id)
        if model is None:
            return None
        model.title = note.title
        model.content = note.content
        self.session.flush()
        return note
```

---

## Testing with SQLAlchemy

```python
import pytest
from core.infrastructure.database import DatabaseSession, Base
from capabilities.notes.infrastructure.repositories import SQLAlchemyNoteRepository
from capabilities.notes.domain.entities import Note


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    db = DatabaseSession("sqlite:///:memory:")
    db.create_tables()
    with db.session() as session:
        yield session


def test_create_and_retrieve_note(db_session):
    repo = SQLAlchemyNoteRepository(db_session)
    
    note = Note(id="123", title="Test Note", content="Hello")
    repo.add(note)
    db_session.commit()
    
    retrieved = repo.get("123")
    assert retrieved is not None
    assert retrieved.title == "Test Note"


def test_list_all_notes(db_session):
    repo = SQLAlchemyNoteRepository(db_session)
    
    repo.add(Note(id="1", title="First", content=""))
    repo.add(Note(id="2", title="Second", content=""))
    db_session.commit()
    
    notes = repo.list_all()
    assert len(notes) == 2
```

---

## Key Differences from Native DB

| Aspect | Native DB | ORM DB |
|--------|-----------|--------|
| **Handlers** | One per database type | Single `DatabaseSession` for all |
| **Queries** | Raw SQL strings | ORM model methods |
| **Schema** | Manual `CREATE TABLE` | `db.create_tables()` |
| **Transactions** | Manual `commit()` per handler | Session-based transactions |
| **Migrations** | Manual scripts | Alembic integration ready |

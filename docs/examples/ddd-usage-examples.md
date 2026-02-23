# DDD Service — Usage Examples

Basic examples demonstrating the DDD hexagonal architecture in practice.

> **See also:** [Core concepts](../ddd-service.md) · [External API calls](ddd-external-api.md) · [Bank balance alert](ddd-bank-balance-alert.md)

---

## Minimal end-to-end demo (in-memory)

A quick example wiring all layers together:

```python
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository
from modules.example_feature.application.use_cases import CreateNote, ListNotes

repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

create_note.execute("First note")
print(list_notes.execute())
```

---

## Wiring with FastAPI

Example composition and HTTP handler:

```python
# composition.py
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository
from modules.example_feature.application.use_cases import CreateNote, ListNotes

repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)
```

```python
# api/notes.py
from fastapi import APIRouter
from pydantic import BaseModel
from .composition import create_note, list_notes

router = APIRouter(prefix="/notes", tags=["notes"])


class CreateNotePayload(BaseModel):
    title: str


@router.post("/")
def create_note_endpoint(payload: CreateNotePayload):
    note = create_note.execute(title=payload.title)
    return {
        "id": note.id,
        "title": note.title,
        "created_at": note.created_at.isoformat(),
    }


@router.get("/")
def list_notes_endpoint():
    return [
        {"id": n.id, "title": n.title, "created_at": n.created_at.isoformat()}
        for n in list_notes.execute()
    ]
```

---

## Swapping implementations

The power of ports-and-adapters: swap the repository without touching use-cases.

```python
# For tests — use in-memory
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository
repo = InMemoryNoteRepository()

# For production — use PostgreSQL (same interface)
from modules.example_feature.infrastructure.postgres_repository import PostgresNoteRepository
repo = PostgresNoteRepository(connection_string="postgresql://...")

# Use-case stays the same
create_note = CreateNote(repo)
```

---

## Testing with mocks

```python
import pytest
from unittest.mock import Mock
from modules.example_feature.application.use_cases import CreateNote
from modules.example_feature.domain.ports import NoteRepository


def test_create_note():
    mock_repo = Mock(spec=NoteRepository)
    mock_repo.add.return_value = Mock(id="123", title="Test", created_at="2026-01-01")
    
    use_case = CreateNote(mock_repo)
    result = use_case.execute("Test")
    
    mock_repo.add.assert_called_once()
    assert result.id == "123"
```

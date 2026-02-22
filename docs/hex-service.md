# Hex Service (hex/DDD-flavored Python)

A pragmatic, per-feature layout that keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

## Expected layout (after scaffold)
```
project/
  src/
    core/{domain,infrastructure,services}
    modules/<feature>/{domain,services,infrastructure}
    utils/
    config/
    main.py
  tests/{unit,integration,performance}/
  container/
  bin/
  data/
  docs/
  public/
  .github/workflows/
  .vscode/
  .env
  pyproject.toml
```

## Domain (core/domain or modules/<feature>/domain)
What goes here: Entities, value objects, domain services (pure business logic), and the ports (interfaces) the domain needs. No framework or I/O.

Example entity: [templates/hex-service/src/modules/example_feature/domain/entities.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/domain/entities.py#L1-L15)
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Note:
    id: str
    title: str
    created_at: datetime
```

Example port: [templates/hex-service/src/modules/example_feature/domain/ports.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/domain/ports.py#L1-L24)
```python
from abc import ABC, abstractmethod
from typing import Iterable
from .entities import Note

class NoteRepository(ABC):
    @abstractmethod
    def add(self, note: Note) -> Note: ...
    @abstractmethod
    def get(self, note_id: str) -> Note | None: ...
    @abstractmethod
    def list(self) -> Iterable[Note]: ...
```

## Application/Services (core/services or modules/<feature>/services)
What goes here: Use-case orchestration; coordinates domain objects and ports. Enforces transaction boundaries and policies; still framework-free.

Example use-case: [templates/hex-service/src/modules/example_feature/services/use_cases.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/services/use_cases.py#L1-L30)
```python
from datetime import datetime
import uuid
from ..domain.entities import Note
from ..domain.ports import NoteRepository

class CreateNote:
    def __init__(self, repo: NoteRepository):
        self.repo = repo

    def execute(self, title: str) -> Note:
        note = Note(id=uuid.uuid4().hex, title=title, created_at=datetime.utcnow())
        return self.repo.add(note)
```

## Infrastructure (core/infrastructure or modules/<feature>/infrastructure)
What goes here: Adapters implementing ports (DB, HTTP clients, brokers), configuration glue, persistence mappers. Keep side effects here.

Example adapter implementing the repository port: [templates/hex-service/src/modules/example_feature/infrastructure/repositories.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/infrastructure/repositories.py#L1-L25)
```python
from ..domain.entities import Note
from ..domain.ports import NoteRepository

class InMemoryNoteRepository(NoteRepository):
    def __init__(self):
        self._items: dict[str, Note] = {}

    def add(self, note: Note) -> Note:
        self._items[note.id] = note
        return note
```

Shared database backends live under `core/infrastructure/database/`, with runtime selection handled in [templates/hex-service/src/main.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/main.py#L22-L133) using `DB_BACKEND` (json, csv, sqlite, postgresql, mariadb, mysql).

## Modules (modules/<feature>)
What goes here: Feature/bounded-context composition—wire domain + app + infra for that feature. Also entrypoints like API/CLI handlers.

Example wiring and handler sketch:
```python
# composition
repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

# API handler (FastAPI-style example)
from fastapi import APIRouter
router = APIRouter()

@router.post("/notes")
def create_note_endpoint(payload: CreateNotePayload):
    note = create_note.execute(title=payload.title)
    return {"id": note.id, "title": note.title, "created_at": note.created_at.isoformat()}
```

## Rules of thumb
- Domain: pure logic and contracts; no I/O or frameworks.
- Services/App: orchestrate use-cases, transactions, and policies; still framework-free.
- Infrastructure: all I/O adapters implementing ports (DB, HTTP, queues, files).
- Modules: group everything per feature/context and provide entrypoints/wiring. Keep core only for truly shared cross-cutting pieces.

## Minimal end-to-end demo (in-memory)
```python
repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

create_note.execute("First note")
print(list_notes.execute())
```

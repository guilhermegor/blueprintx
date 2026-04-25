# **DDD Service — ORM DB (Domain-Driven Design, hexagonal service with SQLAlchemy)**

A Domain-Driven Design scaffold with a hexagonal (ports-and-adapters) layout. It keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

This template uses **SQLAlchemy ORM** for database operations, providing a unified abstraction layer that works with PostgreSQL, MySQL, SQLite, Oracle, MSSQL, and other SQLAlchemy-supported databases.

> **Examples:** [Usage with SQLAlchemy](examples-orm/ddd-orm-usage-examples.md) · [External API Calls](examples-orm/ddd-orm-external-api.md) · [Bank Balance Alert](examples-orm/ddd-orm-bank-balance-alert.md)

---

## Key Differences from Native DB

| Aspect | Native DB | ORM DB (this template) |
|--------|-----------|------------------------|
| **Database access** | Direct SQL via native libraries | SQLAlchemy ORM models |
| **Supported DBs** | Each DB needs its own handler | Any SQLAlchemy-supported DB |
| **Query style** | Raw SQL strings | Python objects & methods |
| **Schema** | Manual table creation | Auto-generated from models |
| **Learning curve** | Simpler for SQL experts | Better for ORM users |

---

## Expected layout (after scaffold)

```bash
project/
  src/
    chassis/
      db_schema/
        domain/
        infrastructure/
          base.py          # SQLAlchemy base, session manager
          models.py        # ORM models
          repository.py    # Generic SQLAlchemy repository
        application/
    capabilities/<feature>/{domain,application,infrastructure}
    utils/
    config/
    main.py
  tests/{unit,integration,performance}/
  container/
    scripts/
  assets/
  docs/
  .github/workflows/
  .vscode/
  .env
  pyproject.toml
```

---

## Folder Descriptions

| Folder | Purpose | Expected Content |
|--------|---------|------------------|
| `src/` | Main source code | All Python modules, organized by DDD layers |
| `src/chassis/` | Shared infrastructure providers | Self-contained providers (db_schema, queues, cache, …) each with their own DDD layers |
| `src/chassis/db_schema/domain/` | Shared domain layer | Base entities, value objects, shared domain services |
| `src/chassis/db_schema/application/` | Shared application layer | Factories, shared use-cases, cross-cutting orchestration |
| `src/chassis/db_schema/infrastructure/` | Shared infrastructure | ORM base, session manager, repository ABC, and ORM models |
| `src/capabilities/<feature>/` | Feature-specific code | Bounded context with its own domain, application, and infrastructure layers |
| `src/utils/` | Utility functions | Helpers, formatters, validators, decorators |
| `src/config/` | Configuration | Settings, environment loaders, constants |
| `tests/unit/` | Unit tests | Fast, isolated tests for domain logic and use-cases |
| `tests/integration/` | Integration tests | Tests with real databases, APIs, or external services |
| `tests/performance/` | Performance tests | Load tests, benchmarks, stress tests |
| `container/` | Container configuration | Dockerfile, docker-compose.yaml, container scripts |
| `container/scripts/` | Container scripts | Entrypoint scripts, health checks, init scripts |
| `assets/` | Static resources | Images, icons, fonts, static files |
| `data/` | Data storage | SQLite databases, CSV files, XLSX files, JSON data, seed data |
| `docs/` | Documentation | API docs, architecture diagrams, user guides |
| `.github/workflows/` | CI/CD pipelines | GitHub Actions workflows for tests, linting, deployment |
| `.vscode/` | Editor settings | VS Code workspace settings, extensions, launch configs |

---

## Layers

### Domain (`chassis/db_schema/domain` or `capabilities/<feature>/domain`)

**What goes here:** Four files with distinct responsibilities — no framework or I/O anywhere in this layer.

| File | Purpose |
|------|---------|
| `entities.py` | Persistence shape — maps to a DB row (`id`, timestamps, status) |
| `dto.py` | Network shape — inbound payload (no `id`) and outbound response |
| `enums.py` | Domain-typed constants shared by entities and DTOs |
| `ports.py` | `Protocol` interfaces infrastructure must satisfy (no inheritance needed) |

```python
# enums.py
from enum import Enum

class NoteStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
```

```python
# entities.py — persistence model (maps to a DB row)
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from .enums import NoteStatus

@dataclass
class Note:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: NoteStatus = NoteStatus.DRAFT
```

```python
# dto.py — network model (what goes over the wire)
from dataclasses import dataclass
from datetime import datetime
from .enums import NoteStatus

@dataclass
class NoteCreateDTO:      # inbound — no id, assigned by the system
    title: str

@dataclass
class NoteResponseDTO:    # outbound
    id: str
    title: str
    created_at: datetime
    status: NoteStatus
```

```python
# ports.py — Protocol, not ABC: infra satisfies it structurally, no import needed
from typing import Iterable, Protocol
from .entities import Note

class NoteRepository(Protocol):
    def add(self, note: Note) -> Note: ...
    def get(self, note_id: str) -> Note | None: ...
    def list(self) -> Iterable[Note]: ...
```

---

### Application (`chassis/db_schema/application` or `capabilities/<feature>/application`)

**What goes here:** Use-case orchestration; coordinates domain objects and ports. Enforces transaction boundaries and policies; still framework-free.

```python
# use_cases.py
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

---

### Infrastructure (`chassis/db_schema/infrastructure` or `capabilities/<feature>/infrastructure`)

**What goes here:** Adapters implementing ports (DB, HTTP clients, brokers), configuration glue, persistence mappers. Keep side effects here.

```python
# repositories.py
from ..domain.entities import Note
from ..domain.ports import NoteRepository

class InMemoryNoteRepository(NoteRepository):
    def __init__(self):
        self._items: dict[str, Note] = {}

    def add(self, note: Note) -> Note:
        self._items[note.id] = note
        return note
```

Shared ORM infrastructure lives under `chassis/db_schema/infrastructure/`, with runtime selection via `DB_BACKEND` env var (sqlite, postgresql, mysql, mariadb, mssql, oracle).

---

### Capabilities (`capabilities/<feature>`)

**What goes here:** Feature/bounded-context composition — wire domain + app + infra for that feature. Also entrypoints like API/CLI handlers.

---

## Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or frameworks |
| **Application** | Orchestrate use-cases, transactions, and policies; still framework-free |
| **Infrastructure** | All I/O adapters implementing ports (DB, HTTP, queues, files) |
| **Capabilities** | Group everything per feature/context and provide entrypoints/wiring |

Keep `chassis/` only for truly shared cross-cutting providers (db_schema, queues, cache, …).

---

## Learn more

- [Example - External API Calls](examples/ddd-external-api.md) — Stock exchange data, swapping providers
- [Example - Wiring with FastAPI](examples/ddd-usage-examples.md) — Wiring, FastAPI integration, testing
- [Example - Bank Balance Alert](examples/ddd-bank-balance-alert.md) — Complete multi-port example

---

## 📚 Acknowledgments

This skeleton is inspired by the foundational work of **Eric Evans** in his seminal book *Domain-Driven Design: Tackling Complexity in the Heart of Software*. If you're new to DDD or want to deepen your understanding of the patterns used here, we highly recommend reading it.

📖 [Domain-Driven Design: Tackling Complexity in the Heart of Software](https://www.amazon.com.br/Domain-Driven-Design-Tackling-Complexity-Software/dp/0321125215) — Eric Evans


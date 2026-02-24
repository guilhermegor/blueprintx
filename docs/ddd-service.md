# **DDD Service (Domain-Driven Design, hexagonal service)**

A Domain-Driven Design scaffold with a hexagonal (ports-and-adapters) layout. It keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

> **Examples:** [External API Calls](examples/ddd-external-api.md) · [Wiring with FastAPI](examples/ddd-usage-examples.md) · [Bank Balance Alert](examples/ddd-bank-balance-alert.md)

---

## Expected layout (after scaffold)

```bash
project/
  src/
    core/{domain,infrastructure,application}
    modules/<feature>/{domain,application,infrastructure}
    utils/
    config/
    main.py
  tests/{unit,integration,performance}/
  container/
    scripts/
  assets/
  data/
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
| `src/core/` | Shared cross-cutting code | Domain entities, infrastructure adapters, and application services used across multiple features |
| `src/core/domain/` | Shared domain layer | Base entities, value objects, shared domain services |
| `src/core/application/` | Shared application layer | Factories, shared use-cases, cross-cutting orchestration |
| `src/core/infrastructure/` | Shared infrastructure | Database handlers, HTTP clients, message brokers, external integrations |
| `src/modules/<feature>/` | Feature-specific code | Bounded context with its own domain, application, and infrastructure layers |
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

### Domain (`core/domain` or `modules/<feature>/domain`)

**What goes here:** Entities, value objects, domain services (pure business logic), and the ports (interfaces) the domain needs. No framework or I/O.

```python
# entities.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Note:
    id: str
    title: str
    created_at: datetime
```

```python
# ports.py
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

---

### Application (`core/application` or `modules/<feature>/application`)

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

### Infrastructure (`core/infrastructure` or `modules/<feature>/infrastructure`)

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

Shared database backends live under `core/infrastructure/database/`, with runtime selection via `DB_BACKEND` env var (json, csv, sqlite, postgresql, mariadb, mysql, mssql, oracle).

---

### Modules (`modules/<feature>`)

**What goes here:** Feature/bounded-context composition — wire domain + app + infra for that feature. Also entrypoints like API/CLI handlers.

---

## Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or frameworks |
| **Application** | Orchestrate use-cases, transactions, and policies; still framework-free |
| **Infrastructure** | All I/O adapters implementing ports (DB, HTTP, queues, files) |
| **Modules** | Group everything per feature/context and provide entrypoints/wiring |

Keep `core/` only for truly shared cross-cutting pieces.

---

## Learn more

- [Example - External API Calls](examples/ddd-external-api.md) — Stock exchange data, swapping providers
- [Example - Wiring with FastAPI](examples/ddd-usage-examples.md) — Wiring, FastAPI integration, testing
- [Example - Bank Balance Alert](examples/ddd-bank-balance-alert.md) — Complete multi-port example

---

## 📚 Acknowledgments

This skeleton is inspired by the foundational work of **Eric Evans** in his seminal book *Domain-Driven Design: Tackling Complexity in the Heart of Software*. If you're new to DDD or want to deepen your understanding of the patterns used here, we highly recommend reading it.

📖 [Domain-Driven Design: Tackling Complexity in the Heart of Software](https://www.amazon.com.br/Domain-Driven-Design-Tackling-Complexity-Software/dp/0321125215) — Eric Evans


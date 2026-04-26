# **DDD Service — ORM DB (Domain-Driven Design, hexagonal service with SQLAlchemy)**

A Domain-Driven Design scaffold with a hexagonal (ports-and-adapters) layout. It keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

This template uses **SQLAlchemy ORM (≥ 2.0)** for database operations, providing a unified abstraction layer that works with PostgreSQL, MySQL, SQLite, Oracle, MSSQL, and any other SQLAlchemy-supported database. Schema creation, session management, and the generic repository are all handled by the chassis — feature code only touches domain types.

> **Examples:** [Usage with SQLAlchemy](examples-orm/ddd-orm-usage-examples.md) · [External API Calls](examples-orm/ddd-orm-external-api.md) · [Bank Balance Alert](examples-orm/ddd-orm-bank-balance-alert.md)

---

## ⚖️ Key Differences from Native DB

| Aspect | Native DB | ORM DB (this template) |
|--------|-----------|------------------------|
| **Database access** | Direct SQL via native libraries | SQLAlchemy ORM models |
| **Supported DBs** | Each DB needs its own handler | Any SQLAlchemy-supported DB |
| **Query style** | Raw SQL strings | Python objects and methods |
| **Schema management** | Manual table creation | Auto-generated from `Base` models via `create_tables()` |
| **Session lifecycle** | Managed per handler | Managed by `DatabaseSession`; repos call `flush()`, use-cases call `commit()` |
| **Schema-less storage** | `db_wschema/` (JSON, CSV, joblib) | Not included — use native-DB template if needed |

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/
    app/
      bootstrap.py          # env loading, logging, elapsed-time tracking
      container.py          # composition root — AppContainer
    capabilities/<feature>/
      domain/               # entities.py · dto.py · enums.py · ports.py
      application/          # use_cases.py · factories.py
      infrastructure/       # repositories.py
    chassis/
      db_schema/
        domain/entities.py
        application/database_factory.py   # build_database_url() + build_database_session()
        infrastructure/
          base.py           # Base (DeclarativeBase) + DatabaseSession + Repository ABC
          models.py         # RecordModel ORM model (add feature models here)
          repository.py     # SQLAlchemyRecordRepository (generic reference impl)
      typing/
        abc_type_checker.py
        protocol_type_checker.py
        type_checker.py
        validate.py
        decorators.py
    config/
      startup.py            # logger, webhooks, runtime constants (module-level singletons)
      inputs.yaml
      outputs.yaml
      webhooks.yaml
      emails.yaml
      signatures/           # email HTML templates
    main.py
  tests/{unit,integration,performance}/
  container/
  bin/
  data/
  assets/
  docs/
  .github/workflows/
  .env
  pyproject.toml
```

---

## 📁 Folder Descriptions

| Folder | Purpose | Expected Content |
|--------|---------|------------------|
| `src/` | Main source code | All Python modules, organised by DDD layers |
| `src/app/` | Service wiring | `bootstrap.py` (env/logging/timing) and `container.py` (composition root) |
| `src/chassis/` | Shared cross-cutting providers | Self-contained providers each with their own DDD sub-layers |
| `src/chassis/db_schema/` | ORM infrastructure | `build_database_session()` factory, `Base`, `DatabaseSession`, `Repository` ABC, `RecordModel` |
| `src/chassis/typing/` | Runtime type enforcement | `ABCTypeCheckerMeta`, `ProtocolTypeCheckerMeta`, `TypeChecker`, `validate` decorators |
| `src/capabilities/<feature>/` | Feature-specific code | Bounded context with its own domain, application, and infrastructure layers |
| `src/config/` | Configuration | `startup.py` (shared singletons), YAML files for outputs, webhooks, inputs, emails |
| `tests/unit/` | Unit tests | Fast, isolated tests for domain logic and use-cases |
| `tests/integration/` | Integration tests | Tests with real databases, APIs, or external services |
| `tests/performance/` | Performance tests | Load tests, benchmarks, stress tests |
| `container/` | Container configuration | Dockerfile, docker-compose.yaml, container scripts |
| `bin/` | Shell helpers | Entry-point scripts called by the `Makefile` |
| `assets/` | Static resources | Images, icons, fonts, static files |
| `data/` | Data storage | SQLite databases, CSV files, JSON data, seed data |
| `docs/` | Documentation | API docs, architecture diagrams, user guides |
| `.github/workflows/` | CI/CD pipelines | GitHub Actions workflows for tests, linting, deployment |

---

## 🏗️ Layers

### Domain (`capabilities/<feature>/domain`)

**What goes here:** Four files with distinct responsibilities — no ORM imports, no framework code anywhere in this layer.

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
# entities.py — pure dataclass, no SQLAlchemy in the domain layer
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
# ports.py — Protocol: infra satisfies it structurally, no import needed
from typing import Iterable, Protocol
from chassis.typing import ProtocolTypeCheckerMeta
from .entities import Note

class NoteRepository(Protocol, metaclass=ProtocolTypeCheckerMeta):
    def add(self, cls_note: Note) -> Note: ...
    def get(self, str_note_id: str) -> Note | None: ...
    def list(self) -> Iterable[Note]: ...
```

---

### Application (`capabilities/<feature>/application`)

**What goes here:** Use-case orchestration; coordinates domain objects and ports. Enforces transaction boundaries; still framework-free. **Never call `session.commit()` here** — the caller (use-case or FastAPI endpoint) controls transaction boundaries.

```python
# use_cases.py
from datetime import datetime
import uuid
from ..domain.dto import NoteCreateDTO, NoteResponseDTO
from ..domain.entities import Note
from ..domain.ports import NoteRepository

def create_note(cls_dto: NoteCreateDTO, cls_repo: NoteRepository) -> NoteResponseDTO:
    cls_note = Note(id=uuid.uuid4().hex, title=cls_dto.title, created_at=datetime.utcnow())
    cls_stored = cls_repo.add(cls_note)
    return NoteResponseDTO(
        id=cls_stored.id,
        title=cls_stored.title,
        created_at=cls_stored.created_at,
        status=cls_stored.status,
    )
```

---

### Infrastructure (`capabilities/<feature>/infrastructure`)

**What goes here:** Adapters implementing domain ports. Session-backed repos extend `Repository` from `chassis/db_schema/infrastructure/base.py` and accept a `Session` via constructor (DI — never call `DatabaseSession` directly inside a repository).

```python
# repositories.py — in-memory starter; replace with a Session-backed impl
from typing import Iterable
from chassis.typing import TypeChecker
from ..domain.entities import Note

class InMemoryNoteRepository(metaclass=TypeChecker):
    def __init__(self) -> None:
        self._dict_items: dict[str, Note] = {}

    def add(self, cls_note: Note) -> Note:
        self._dict_items[cls_note.id] = cls_note
        return cls_note

    def get(self, str_note_id: str) -> Note | None:
        return self._dict_items.get(str_note_id)

    def list(self) -> Iterable[Note]:
        return self._dict_items.values()
```

**Session-backed example:**

```python
from sqlalchemy.orm import Session
from chassis.db_schema.infrastructure.base import Repository
from chassis.db_schema.infrastructure.models import RecordModel
from ..domain.entities import Note

class SQLNoteRepository(Repository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def add(self, cls_note: Note) -> Note:
        cls_model = RecordModel(id=cls_note.id, data={"title": cls_note.title})
        self.session.add(cls_model)
        self.session.flush()   # assigns DB id without committing
        return cls_note
```

The caller (use-case layer or endpoint) calls `session.commit()` after the repo method returns.

---

### Chassis

**What goes here:** Shared ORM infrastructure consumed by all features.

**`Base`** (`chassis/db_schema/infrastructure/base.py`) — `DeclarativeBase` subclass all ORM models inherit from. `DatabaseSession.create_tables()` / `drop_tables()` operate on `Base.metadata`.

**`DatabaseSession`** — session manager; two access modes:

```python
from chassis.db_schema.application import build_database_session

cls_db = build_database_session()
cls_db.create_tables()

# Explicit context (scripts, CLI):
with cls_db.session() as session:
    cls_repo = SQLNoteRepository(session)
    cls_repo.add(cls_note)
    session.commit()

# Generator for FastAPI Depends injection:
@app.get("/notes")
def list_notes(session: Session = Depends(cls_db.get_session)):
    cls_repo = SQLNoteRepository(session)
    return cls_repo.list_all()
```

**`Repository` ABC** — abstract CRUD contract (`add / get / update / delete / list_all`). Uses `ABCTypeCheckerMeta` (not `Protocol`) because shared session-handling logic lives in the base. Feature repositories extend it and receive a `Session` in `__init__`.

**`SQLAlchemyRecordRepository`** (`chassis/db_schema/infrastructure/repository.py`) — generic implementation that stores any dict as a JSON blob in `RecordModel`. Use it as the reference to copy and adapt per feature.

**`build_database_session()`** (`chassis/db_schema/application/database_factory.py`) — reads `DB_BACKEND` from `.env`:

```python
from chassis.db_schema.application import build_database_session

# .env: DB_BACKEND=postgresql  DB_HOST=localhost  DB_NAME=app
cls_db = build_database_session()
```

Supported backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.  
All non-SQLite backends read `DB_DSN` first; if unset they compose a URL from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`.

**Adding a new ORM model** — add a class inheriting from `Base` in `chassis/db_schema/infrastructure/models.py` (or a feature-local models file that is imported there). `create_tables()` will pick it up automatically.

**Adding a new chassis provider** — create `chassis/<provider>/{domain,application,infrastructure}/` following the same sub-layer pattern.

---

### App (`src/app/`)

**What goes here:** Service wiring that runs once at startup — not business logic.

`bootstrap.py` loads `.env`, configures logging, suppresses `FutureWarning`, and returns a monotonic start timestamp.

`container.py` is the **composition root**: instantiates `DatabaseSession`, calls `create_tables()`, creates repositories, and returns a frozen `AppContainer` of fully-bound entry points:

```python
# container.py pattern
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class AppContainer:
    create_note: Callable[[NoteCreateDTO], NoteResponseDTO]
    list_notes: Callable[[], list[NoteResponseDTO]]

def build() -> AppContainer:
    cls_db = build_database_session()
    cls_db.create_tables()
    cls_session = cls_db.session()
    cls_note_repo = SQLNoteRepository(cls_session)
    return AppContainer(
        create_note=lambda cls_dto: create_note(cls_dto, cls_note_repo),
        list_notes=lambda: list_notes(cls_note_repo),
    )
```

`main.py` only calls `init()`, `build()`, the bound entry points, and `teardown()` — no logic lives there.

---

### Config (`src/config/`)

**What goes here:** Module-level singletons initialised once at import time, plus YAML config files read at startup.

`startup.py` exposes: `LOGGER`, `ENVIRONMENT`, `APP_NAME`, `USER`, `HOSTNAME`, `CLS_MS_TEAMS`, `YAML_OUTPUTS`, `YAML_INPUTS`, `YAML_WEBHOOKS`, `PATH_LOG`, `PATH_JSON`.

YAML files hold URL, path template, and query string configuration. Keep credentials in `.env`, not in YAML.

---

## 🔄 Session lifecycle rule

| Location | What to call | Why |
|----------|-------------|-----|
| Repository method | `session.flush()` | Assigns DB-generated IDs without ending the transaction |
| Use-case / caller | `session.commit()` | Caller controls the transaction boundary |
| Repository method | ~~`session.commit()`~~ | Never — the repository must not decide when a transaction ends |

This rule keeps transactions composable: a use-case can call multiple repo methods in one atomic commit.

---

## 📐 Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or ORM imports |
| **Application** | Orchestrate use-cases and policies; still framework-free |
| **Infrastructure** | Session-backed repo implementations and ORM model mapping |
| **Chassis** | Shared ORM base, session manager, generic repository, and type enforcement |
| **App** | Service bootstrap and composition root only; no business logic |
| **Config** | Shared runtime constants and YAML-driven configuration; secrets stay in `.env` |

Keep `chassis/` only for truly shared cross-cutting providers. Feature-specific ORM models and repos belong in `capabilities/<feature>/infrastructure/`.

---

## 🔗 Learn more

- [Example - Usage with SQLAlchemy](examples-orm/ddd-orm-usage-examples.md) — Wiring ORM layers, session management, FastAPI integration
- [Example - External API Calls](examples-orm/ddd-orm-external-api.md) — Consuming external APIs in an ORM-based service
- [Example - Bank Balance Alert](examples-orm/ddd-orm-bank-balance-alert.md) — Complete multi-port ORM example

---

## 🙏 Acknowledgments

This skeleton is inspired by the foundational work of **Eric Evans** in his seminal book *Domain-Driven Design: Tackling Complexity in the Heart of Software*. If you're new to DDD or want to deepen your understanding of the patterns used here, we highly recommend reading it.

[Domain-Driven Design: Tackling Complexity in the Heart of Software](https://www.amazon.com.br/Domain-Driven-Design-Tackling-Complexity-Software/dp/0321125215) — Eric Evans

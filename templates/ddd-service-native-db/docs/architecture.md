# **Architecture — DDD Service (Native DB)**

A hexagonal (ports-and-adapters) architecture with Domain-Driven Design layers. Business logic is isolated from I/O — all side effects live in the infrastructure layer.

This skeleton uses **native database libraries** (psycopg2, sqlite3, cx_Oracle, pyodbc, pymysql) for direct database access. For schema-less persistence the same `DatabaseHandler` contract covers JSON, CSV, and joblib backends via `chassis/db_wschema/`.

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
      db/
        domain/ports.py             # DatabaseHandler ABC + Record type
        infrastructure/helpers.py   # ensure_id helper
      db_schema/
        application/database_factory.py   # build_database_handler()
        infrastructure/
          sqlite_handler.py
          postgres_handler.py
          mariadb_handler.py
          mysql_handler.py
          mssql_handler.py
          oracle_handler.py
      db_wschema/
        application/storage_factory.py    # build_storage_handler()
        infrastructure/
          json_handler.py
          csv_handler.py
          joblib_handler.py
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
| `src/capabilities/<feature>/domain/` | Pure business logic | `entities.py`, `dto.py`, `enums.py`, `ports.py` — no I/O |
| `src/capabilities/<feature>/application/` | Use-case orchestration | `use_cases.py` — no framework or DB imports |
| `src/capabilities/<feature>/infrastructure/` | Adapters implementing ports | `repositories.py` — all DB and HTTP calls |
| `src/chassis/db/` | Shared DB contract | `DatabaseHandler` ABC, `Record` type alias, `ensure_id` helper |
| `src/chassis/db_schema/` | SQL-backed handlers | `build_database_handler()` factory + six SQL backend handlers |
| `src/chassis/db_wschema/` | Schema-less handlers | `build_storage_handler()` factory + JSON, CSV, Joblib handlers |
| `src/config/` | Runtime configuration | `startup.py` for singletons; YAML config files; secrets in `.env` |
| `tests/unit/` | Isolated domain tests | Fast tests with no I/O — mock at infrastructure boundaries |
| `tests/integration/` | Integration tests | Tests using real databases, APIs, or external services |
| `docs/` | Project documentation | This MkDocs site |

---

## Layers

### Domain (`capabilities/<feature>/domain`)

**What goes here:** Four files with distinct responsibilities — no framework or I/O anywhere in this layer.

```python
# enums.py — domain-typed constants
from enum import Enum

class NoteStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
```

```python
# entities.py — persistence shape (maps to a DB row)
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
# ports.py — Protocol, not ABC: infrastructure satisfies it structurally (no import needed)
from typing import Iterable, Protocol
from .entities import Note

class NoteRepository(Protocol):
    def add(self, cls_note: Note) -> Note: ...
    def get(self, str_note_id: str) -> Note | None: ...
    def list(self) -> Iterable[Note]: ...
```

### Application (`capabilities/<feature>/application`)

**What goes here:** Use-case orchestration. Coordinates domain objects and ports. Enforces transaction boundaries and policies — still framework-free.

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

**What goes here:** Adapters implementing domain ports. All side effects (DB calls, HTTP requests, file writes) live here.

```python
# repositories.py — in-memory starter; replace with a DatabaseHandler-backed impl
from typing import Iterable
from ..domain.entities import Note

class InMemoryNoteRepository:
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

To swap to a persistent backend, accept a `DatabaseHandler` in `__init__` and delegate to `create / read / update / delete`.

### Chassis

**What goes here:** Reusable cross-cutting providers shared by all features. Each sub-provider has its own `domain/`, `application/`, `infrastructure/` sub-layers.

```python
# main.py — wiring example
from chassis.db_schema.application import build_database_handler
from chassis.db_wschema.application import build_storage_handler

# reads DB_BACKEND from .env — e.g. DB_BACKEND=sqlite  DB_PATH=./data/app.db
cls_db = build_database_handler()

# reads STORAGE_BACKEND from .env — e.g. STORAGE_BACKEND=json  DATA_DIR=./data
cls_storage = build_storage_handler()
```

Supported SQL backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.

Supported schema-less backends: `json`, `csv`, `joblib`.

---

## Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or frameworks |
| **Application** | Orchestrate use-cases and policies; framework-free |
| **Infrastructure** | All I/O adapters implementing domain ports |
| **Chassis** | Reusable cross-cutting providers (DB handlers, schema-less storage) |
| **Config** | Shared runtime constants; secrets stay in `.env` |

Keep `chassis/` only for truly shared cross-cutting providers. Feature-specific persistence belongs in `capabilities/<feature>/infrastructure/`.

---

## Learn more

- [API Reference](api.md) — factory usage, use-case wiring, and extension patterns

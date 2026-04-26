# **DDD Service — Native DB (Domain-Driven Design, hexagonal service)**

A Domain-Driven Design scaffold with a hexagonal (ports-and-adapters) layout. It keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

This template uses **native database libraries** (psycopg2, sqlite3, cx_Oracle, pyodbc, pymysql, etc.) for direct database access, giving you fine-grained control over queries and connections. For schema-less persistence the same `DatabaseHandler` contract covers JSON, CSV, and joblib backends via `chassis/db_wschema/`.

> **Examples:** [External API Calls](examples/ddd-external-api.md) · [Wiring with FastAPI](examples/ddd-usage-examples.md) · [Bank Balance Alert](examples/ddd-bank-balance-alert.md)

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
      db/
        domain/ports.py             # DatabaseHandler ABC + Record type
        infrastructure/helpers.py   # ensure_id helper
      db_schema/
        domain/entities.py
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
          sanity_check.py
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
      queries/              # .sql / .graphql files
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
| `src/chassis/db/` | Shared database contract | `DatabaseHandler` ABC (`ports.py`), `Record` type alias, `ensure_id` helper |
| `src/chassis/db_schema/` | SQL-backed handlers | `build_database_handler()` factory + six SQL backend handlers |
| `src/chassis/db_wschema/` | Schema-less handlers | `build_storage_handler()` factory + JSON, CSV, Joblib handlers + `SanityCheck` |
| `src/chassis/typing/` | Runtime type enforcement | `ABCTypeCheckerMeta`, `ProtocolTypeCheckerMeta`, `TypeChecker`, `validate` decorators |
| `src/capabilities/<feature>/` | Feature-specific code | Bounded context with its own domain, application, and infrastructure layers |
| `src/config/` | Configuration | `startup.py` (shared singletons), YAML files for outputs, webhooks, inputs, emails |
| `tests/unit/` | Unit tests | Fast, isolated tests for domain logic and use-cases |
| `tests/integration/` | Integration tests | Tests with real databases, APIs, or external services |
| `tests/performance/` | Performance tests | Load tests, benchmarks, stress tests |
| `container/` | Container configuration | Dockerfile, docker-compose.yaml, container scripts |
| `bin/` | Shell helpers | Entry-point scripts called by the `Makefile` |
| `assets/` | Static resources | Images, icons, fonts, static files |
| `data/` | Data storage | SQLite databases, CSV files, JSON data, joblib artifacts, seed data |
| `docs/` | Documentation | API docs, architecture diagrams, user guides |
| `.github/workflows/` | CI/CD pipelines | GitHub Actions workflows for tests, linting, deployment |

---

## 🏗️ Layers

### Domain (`capabilities/<feature>/domain`)

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
from chassis.typing import ProtocolTypeCheckerMeta
from .entities import Note

class NoteRepository(Protocol, metaclass=ProtocolTypeCheckerMeta):
    def add(self, cls_note: Note) -> Note: ...
    def get(self, str_note_id: str) -> Note | None: ...
    def list(self) -> Iterable[Note]: ...
```

---

### Application (`capabilities/<feature>/application`)

**What goes here:** Use-case orchestration; coordinates domain objects and ports. Enforces transaction boundaries and policies; still framework-free.

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

def list_notes(cls_repo: NoteRepository) -> list[NoteResponseDTO]:
    return [
        NoteResponseDTO(id=cls_n.id, title=cls_n.title, created_at=cls_n.created_at, status=cls_n.status)
        for cls_n in cls_repo.list()
    ]
```

---

### Infrastructure (`capabilities/<feature>/infrastructure`)

**What goes here:** Adapters implementing domain ports (DB, HTTP clients, brokers). All side effects live here.

```python
# repositories.py — in-memory starter; swap for a DatabaseHandler-backed impl
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

To swap to a persistent backend, accept a `DatabaseHandler` in `__init__` and delegate to `create / read / update / delete`.

---

### Chassis

**What goes here:** Reusable cross-cutting providers shared by all features. Each sub-provider has its own `domain/`, `application/`, `infrastructure/` sub-layers.

**`DatabaseHandler` ABC** (`chassis/db/domain/ports.py`) — the single contract all storage backends implement:

```python
from abc import abstractmethod
from pathlib import Path
from typing import Any
from chassis.typing import ABCTypeCheckerMeta

Record = dict[str, Any]

class DatabaseHandler(metaclass=ABCTypeCheckerMeta):
    @abstractmethod
    def create(self, record: Record) -> str: ...
    @abstractmethod
    def read(self, record_id: str) -> Record | None: ...
    @abstractmethod
    def update(self, record_id: str, updates: Record) -> Record | None: ...
    @abstractmethod
    def delete(self, record_id: str) -> bool: ...
    @abstractmethod
    def backup(self, target_path: str | Path) -> Path: ...
    @abstractmethod
    def close(self) -> None: ...
```

**`build_database_handler()`** (`chassis/db_schema/application/database_factory.py`) — reads `DB_BACKEND` from `.env` and returns a ready handler:

```python
from chassis.db_schema.application import build_database_handler

# .env: DB_BACKEND=sqlite  DB_PATH=./data/app.db
cls_db = build_database_handler()
cls_db.create({"title": "First record"})
```

Supported SQL backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.  
All non-SQLite backends read `DB_DSN` first; if unset they compose a DSN from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`.

**`build_storage_handler()`** (`chassis/db_wschema/application/storage_factory.py`) — reads `STORAGE_BACKEND`:

```python
from chassis.db_wschema.application import build_storage_handler

# .env: STORAGE_BACKEND=json  DATA_DIR=./data
cls_storage = build_storage_handler()
```

Supported schema-less backends: `json`, `csv`, `joblib`.

**`JoblibHandler`** stores immutable binary artifacts. Each artifact is named `name_YYYYMMDD_HHMMSS_{sha256_prefix8}.joblib`. Three-factor integrity on load: SHA256 prefix match, `_saved_at` metadata check, optional HMAC sidecar (set `JOBLIB_SECRET_KEY` in `.env`). `update()` raises `NotImplementedError` — always create a new artifact with `create()`.

**`SanityCheck`** (`chassis/db_wschema/infrastructure/sanity_check.py`) — post-load semantic validator:

```python
from chassis.db_wschema.infrastructure.sanity_check import SanityCheck

cls_check = SanityCheck(expected_class_name="MyModel", required_attrs=["version", "weights"])
cls_check.validate(cls_loaded_obj)
```

**Adding a new SQL backend** — subclass `DatabaseHandler` in `chassis/db_schema/infrastructure/<name>_handler.py`, implement all six abstract methods, export from `chassis/db_schema/infrastructure/__init__.py`, and register the key in `database_factory.py`.

**Adding a new chassis provider** — create `chassis/<provider>/{domain,application,infrastructure}/` following the same sub-layer pattern.

---

### App (`src/app/`)

**What goes here:** Service wiring that runs once at startup — not business logic.

`bootstrap.py` loads `.env`, configures logging, suppresses `FutureWarning`, and returns a monotonic start timestamp.

`container.py` is the **composition root**: it instantiates infrastructure, creates repositories, and returns a frozen `AppContainer` whose callables are fully-bound entry points:

```python
# container.py pattern
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class AppContainer:
    create_note: Callable[[NoteCreateDTO], NoteResponseDTO]
    list_notes: Callable[[], list[NoteResponseDTO]]

def build() -> AppContainer:
    cls_db = build_database_handler()
    cls_note_repo = InMemoryNoteRepository()
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

## 📐 Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or frameworks |
| **Application** | Orchestrate use-cases, transactions, and policies; still framework-free |
| **Infrastructure** | All I/O adapters implementing domain ports (DB, HTTP, queues, files) |
| **Chassis** | Reusable cross-cutting providers (DB handlers, schema-less storage, type enforcement) |
| **App** | Service bootstrap and composition root only; no business logic |
| **Config** | Shared runtime constants and YAML-driven configuration; secrets stay in `.env` |

Keep `chassis/` only for truly shared cross-cutting providers. Feature-specific persistence belongs in `capabilities/<feature>/infrastructure/`.

---

## 🔗 Learn more

- [Example - External API Calls](examples/ddd-external-api.md) — Stock exchange data, swapping providers
- [Example - Wiring with FastAPI](examples/ddd-usage-examples.md) — Wiring, FastAPI integration, testing
- [Example - Bank Balance Alert](examples/ddd-bank-balance-alert.md) — Complete multi-port example

---

## 🙏 Acknowledgments

This skeleton is inspired by the foundational work of **Eric Evans** in his seminal book *Domain-Driven Design: Tackling Complexity in the Heart of Software*. If you're new to DDD or want to deepen your understanding of the patterns used here, we highly recommend reading it.

[Domain-Driven Design: Tackling Complexity in the Heart of Software](https://www.amazon.com.br/Domain-Driven-Design-Tackling-Complexity-Software/dp/0321125215) — Eric Evans

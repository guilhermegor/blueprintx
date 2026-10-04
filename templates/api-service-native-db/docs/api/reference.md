# **API Reference — API Service (Native DB)**

Usage examples for the HTTP transport layer, database factories, use-case wiring, and
extension patterns.

> **See also:** [Architecture](../architecture.md)

---

## Serving the app

`src/app/api.py`'s `create_app()` builds the composition root's container, then mounts each
capability's router — `src/main.py` calls it and hands the result to `uvicorn`.

```python
from app.api import create_app

app = create_app()  # in src/main.py — `app.api` exports create_app() only,
                    # so `uvicorn app.api:app` fails on attribute lookup.
                    # Use `uvicorn main:app` (or `poe run`), or factory mode:
                    # `uvicorn app.api:create_app --factory`
```

`GET /health` is always mounted, unconditionally of any capability — a liveness probe with no
dependencies, so it answers `{"status": "ok"}` even before a capability's router is wired.

---

## Adding an HTTP endpoint to a capability

1. Router lives at `capabilities/<feature>/transport/routers.py`, one `build_<feature>_router()`
   factory that takes plain callables — **never** the `AppContainer` itself (see
   `.layer-policy.yaml`'s `capabilities/*/transport` entry: an inbound adapter must not know the
   container that wires it).
2. Request/response shapes are the capability's existing `dto.py` — FastAPI serializes a stdlib
   `@dataclass` directly, so there is no separate "API schema" to keep in sync with the domain DTO.
3. Mount the router in `src/app/api.py`'s `create_app()`, passing the container's callables in.

```python
# capabilities/example_feature/transport/routers.py
@cls_router.post("", response_model=NoteResponseDTO, status_code=status.HTTP_201_CREATED)
def create_note(cls_dto: NoteCreateDTO) -> NoteResponseDTO:
    return fn_create_note(cls_dto)
```

---

## Database handler factory

`build_database_handler()` reads `DB_BACKEND` from `.env` and returns a ready `DatabaseHandler`.

```python
from chassis.db_schema.application import build_database_handler

# .env: DB_BACKEND=sqlite  DB_PATH=./data/app.db
cls_db = build_database_handler()

# All backends implement the same six-method contract
record_id = cls_db.create({"title": "First record"})
cls_record = cls_db.read(record_id)
cls_db.update(record_id, {"title": "Updated"})
cls_db.delete(record_id)
path_backup = cls_db.backup("./data/backups")
cls_db.close()
```

Supported values for `DB_BACKEND`: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`.

Non-SQLite backends read `DB_DSN` first; if unset they compose a DSN from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`.

⚠️ **Oracle is the exception: it reads `DB_SERVICE` (default `XEPDB1`), not `DB_NAME`.** Setting `DB_NAME` for an Oracle backend is inert — the value is silently ignored and the connection uses the default service.

---

## Schema-less storage factory

`build_storage_handler()` reads `STORAGE_BACKEND` from `.env`.

<!-- docs-refs-ok: chassis/db_wschema is only injected when the storage opt-in is chosen at scaffold time — see templates/python-common/CLAUDE.md -->
```python
from chassis.db_wschema.application import build_storage_handler

# .env: STORAGE_BACKEND=json  DATA_DIR=./data
cls_storage = build_storage_handler()

artifact_id = cls_storage.create({"key": "value"})
cls_record = cls_storage.read(artifact_id)
```

Supported values for `STORAGE_BACKEND`: `json`, `csv`, `joblib`.

!!! note "Joblib artifacts are immutable"
    `JoblibHandler.update()` raises `NotImplementedError`. Always create a new artifact
    with `create()`. Each artifact is named `name_YYYYMMDD_HHMMSS_{sha256_prefix8}.joblib`
    and verified on load with SHA256 prefix matching and optional HMAC.

---

## Wiring a use-case in main.py

<!-- docs-refs-ok: "notes" is the hand-built feature this walkthrough has the reader create following Architecture — it never ships as a generated file, unlike capabilities/example_feature -->
```python
from capabilities.example_feature.application.use_cases import CreateNote, ListNotes
from capabilities.example_feature.domain.entities import Note
from capabilities.example_feature.infrastructure.repositories import InMemoryNoteRepository

cls_repo = InMemoryNoteRepository()

# Create — the use case is a class taking the port at construction,
# and execute() takes the domain entity, not a DTO.
cls_note = CreateNote(cls_repo).execute(Note(title="Hello"))
print(cls_note.id, cls_note.title)

# List
list_notes = ListNotes(cls_repo).execute()
```

---

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Define domain files: `enums.py` (constants), `entities.py` (persistence shape), `dto.py` (network shape), `ports.py` (Protocol interfaces).
3. Write use-cases in `application/use_cases.py` — accept port Protocols as arguments (dependency injection).
4. Implement the port in `infrastructure/repositories.py` using a `DatabaseHandler` from chassis.
5. Add `transport/routers.py` if the capability is reachable over HTTP (see "Adding an HTTP endpoint" above).
6. Wire the container in `app/container.py`, then mount the router in `app/api.py`.

One class per file. No framework or DB imports inside `domain/` or `application/`.

---

## Adding a new SQL backend

Subclass `DatabaseHandler` in `src/chassis/db_schema/infrastructure/<name>_handler.py`, implement all six abstract methods (`create`, `read`, `update`, `delete`, `backup`, `close`), export from `src/chassis/db_schema/infrastructure/__init__.py`, then register the backend key in `database_factory.py`.

---

## Adding a new chassis provider

Create `src/chassis/<provider>/{domain,application,infrastructure}/` following the same DDD sub-layer pattern. Each provider is self-contained and exposes a clean interface consumed by capabilities.

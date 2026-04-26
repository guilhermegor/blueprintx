# **API Reference — DDD Service (Native DB)**

Usage examples for the database factories, use-case wiring, and extension patterns.

> **See also:** [Architecture](architecture.md)

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

---

## Schema-less storage factory

`build_storage_handler()` reads `STORAGE_BACKEND` from `.env`.

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

```python
from capabilities.notes.domain.dto import NoteCreateDTO
from capabilities.notes.infrastructure.repositories import InMemoryNoteRepository
from capabilities.notes import use_cases

cls_repo = InMemoryNoteRepository()

# Create
cls_note = use_cases.create_note(NoteCreateDTO(title="Hello"), cls_repo)
print(cls_note.id, cls_note.title)

# List
list_notes = use_cases.list_notes(cls_repo)
```

---

## Adding a new capability

1. Create `src/capabilities/<feature>/{domain,application,infrastructure}/__init__.py`.
2. Define domain files: `enums.py` (constants), `entities.py` (persistence shape), `dto.py` (network shape), `ports.py` (Protocol interfaces).
3. Write use-cases in `application/use_cases.py` — accept port Protocols as arguments (dependency injection).
4. Implement the port in `infrastructure/repositories.py` using a `DatabaseHandler` from chassis.
5. Wire everything in `main.py`.

One class per file. No framework or DB imports inside `domain/` or `application/`.

---

## Adding a new SQL backend

Subclass `DatabaseHandler` in `src/chassis/db_schema/infrastructure/<name>_handler.py`, implement all six abstract methods (`create`, `read`, `update`, `delete`, `backup`, `close`), export from `src/chassis/db_schema/infrastructure/__init__.py`, then register the backend key in `database_factory.py`.

---

## Adding a new chassis provider

Create `src/chassis/<provider>/{domain,application,infrastructure}/` following the same DDD sub-layer pattern. Each provider is self-contained and exposes a clean interface consumed by capabilities.

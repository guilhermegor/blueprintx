# **API Service — Native DB (hexagonal HTTP service)**

An HTTP API service scaffold: hexagonal DDD layers (domain / application / infrastructure) plus
a **transport** layer — the inbound HTTP adapter that makes this an API service rather than a
batch/pipeline DDD service. Named for the **role** (API service), not the framework: FastAPI is
the transport layer's implementation, confined to `capabilities/*/transport/routers.py` and
`app/api.py`.

This template uses **native database libraries** (psycopg, sqlite3, oracledb, pyodbc,
mysql-connector-python) for direct database access. For schema-less persistence the same
`DatabaseHandler` contract covers JSON, CSV, and joblib backends via `chassis/db_wschema/`
(opt-in at scaffold time).

⚠️ **No registry/publish workflow.** A service is deployed, not published — the release workflow
tags and cuts a GitHub Release only, the same as every other service skeleton (`ddd-service-*`,
`mvc-service-*`). Only `lib-minimal` and `ts-lib` ship a publish flow.

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/
    app/
      bootstrap.py          # env loading, logging, elapsed-time tracking
      container.py          # composition root — AppContainer
      api.py                # create_app() — builds the ASGI app, mounts every router
    capabilities/<feature>/
      domain/               # entities.py · dto.py · enums.py · ports.py
      application/          # use_cases.py · factories.py
      infrastructure/       # repositories.py — outbound adapters (DB, outbound HTTP)
      transport/            # routers.py — inbound HTTP adapter (FastAPI APIRouter)
    chassis/                # db, db_schema, db_wschema (opt-in), typing — same as ddd-service-native-db
    config/
      startup.py · inputs.yaml · outputs.yaml · webhooks.yaml · emails.yaml
      queries/<engine>/     # SQL filed per DB_BACKEND
      query_loader.py
    main.py                 # bootstrap → wire (create_app) → serve (uvicorn) → teardown
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

## 📁 What's different from `ddd-service-native-db`

| Aspect | DDD Service (Native DB) | API Service (Native DB) |
|--------|--------------------------|---------------------------|
| Entry point | `src/main.py` runs a script-style demo (create → list → log) | `src/main.py` builds the ASGI app and blocks on `uvicorn.run()` |
| New layer | — | `capabilities/<feature>/transport/` — FastAPI `APIRouter`, inbound only |
| New composition-root module | — | `src/app/api.py` — `create_app()`, mounts every capability's router + `/health` |
| Runtime dependency | — | `fastapi`, `uvicorn[standard]` |
| `.layer-policy.yaml` | — | Adds `capabilities/*/transport` (allows `fastapi`) and `__root__` allows `uvicorn` |

Everything else — domain/application/infrastructure boundaries, chassis providers, the
`DatabaseHandler` contract, native DB drivers, the runtime type-checking engine — is identical to
`ddd-service-native-db`. See that skeleton's own docs for the shared layers.

---

## 🏗️ The transport layer

**What goes here:** HTTP request/response translation, and nothing else. The router is handed
plain callables by the composition root — **never the container itself** — so it stays testable
and framework-swappable without importing `app/`:

```python
# capabilities/example_feature/transport/routers.py
from fastapi import APIRouter, status
from ..domain.dto import NoteCreateDTO, NoteResponseDTO

def build_example_feature_router(fn_create_note, fn_list_notes) -> APIRouter:
    cls_router = APIRouter(prefix="/notes", tags=["notes"])

    @cls_router.post("", response_model=NoteResponseDTO, status_code=status.HTTP_201_CREATED)
    def create_note(cls_dto: NoteCreateDTO) -> NoteResponseDTO:
        return fn_create_note(cls_dto)

    @cls_router.get("", response_model=list[NoteResponseDTO])
    def list_notes() -> list[NoteResponseDTO]:
        return fn_list_notes()

    return cls_router
```

```python
# app/api.py — the composition root is the only place transport and container meet
from app.container import build
from capabilities.example_feature.transport import build_example_feature_router

def create_app() -> FastAPI:
    cls_container = build()
    cls_app = FastAPI(title="API Service", version="0.0.1")
    cls_app.include_router(
        build_example_feature_router(cls_container.create_note, cls_container.list_notes)
    )
    return cls_app
```

Request/response shapes are the capability's existing `dto.py` — FastAPI serializes a stdlib
`@dataclass` directly (`NoteCreateDTO`/`NoteResponseDTO`), so there is no separate "API schema"
to keep in sync with the domain DTO.

---

## 📐 Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Pure logic and contracts; no I/O or frameworks |
| **Application** | Orchestrate use-cases and policies; framework-free |
| **Infrastructure** | Outbound I/O adapters implementing domain ports (DB, outbound HTTP) |
| **Transport** | Inbound HTTP adapter; request/response translation only, no container knowledge |
| **App** | Composition root — `bootstrap.py`, `container.py`, `api.py`; no business logic |
| **Chassis** | Reusable cross-cutting providers (DB handlers, schema-less storage, type enforcement) |

---

## 🔗 Learn more

Once scaffolded, the project's own `docs/architecture.md` and `docs/api/reference.md` cover the
same material in the generated project's own voice, plus the shared DDD layers.

# **Architecture — MVC Service (ORM)**

A classical Model–View–Controller layout for script/pipeline-style services. The controller reads top to bottom and wires the other layers; the model owns data access; the view owns output rendering.

This skeleton uses the **SQLAlchemy ORM** (≥2.0) — the model declares mapped classes, opens sessions, and shapes query results into pandas DataFrames via `pd.read_sql`. For raw-driver access, use the **MVC Service (Native DB)** skeleton instead.

---

## Expected layout

```bash
project/
  src/
    controller/
      main.py            # script-style entry-point: config → model → view
    model/
      example_entity.py  # DeclarativeBase + ORM model + service class (Session → DataFrame)
    view/
      report_renderer.py # RenderToExcel — DataFrame → .xlsx
    utils/
      __init__.py        # project-specific helpers
      br_identifiers.py  # CNPJ/CPF mask · unmask · validate
      dtypes.py          # apply_dtypes() — explicit column typing on load
    config/
      connection_db.py   # build_engine() / build_session_factory() — SQLAlchemy factories
      startup.py         # logger, runtime constants (module-level singletons)
      inputs.yaml · outputs.yaml · webhooks.yaml · emails.yaml
      signatures/ · queries/
  tests/{unit,integration,performance}/
  docs/
  .env
  pyproject.toml
```

---

## Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Model** | `src/model/` | Data access. ORM models + service classes. May open sessions. Returns pandas DataFrames (or ORM objects). |
| **View** | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB. |
| **Controller** | `src/controller/` | Orchestration. Imports model + view + config. `main.py` is the script-style entry-point. |
| **Utils** | `src/utils/` | Project-specific cross-cutting helpers. The BR calendar comes from the `wwdates` dependency (wrapped by `utils.dates`). |
| **Config** | `src/config/` | `startup.py` builds runtime singletons once at import (logger, webhook, paths) from YAML + `.env`. |

---

## Data access

`config/connection_db.build_engine()` reads `DB_BACKEND` from `.env` and returns a SQLAlchemy `Engine`; `build_session_factory()` returns a bound `sessionmaker`. Supported backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. SQLite is the zero-config default. Set `SQL_ECHO=true` to log SQL. SQL Server adds `DB_MSSQL_AUTH` (`sql` or `aad` for Azure AD Interactive).

`model/example_entity` shows the pattern: a `DeclarativeBase` subclass, an ORM-mapped `ExampleRecord`, and an `ExampleEntity` service that opens sessions for writes and uses `pd.read_sql` for reads.

---

## Session lifecycle

- The service class owns a `sessionmaker`; it opens a session per write and closes it in a `finally`.
- Reads go through `pd.read_sql` on an engine connection — no long-lived session needed.
- Keep `commit()` at the service boundary, never inside a lower-level helper.

---

## Enrichment degradation contract

`controller/_pipeline.PipelineOrchestrator._enrich` is the reference example for a
**documented graceful degradation**. A degradation documented in a docstring ("returns
`None`/unchanged when X") is a claim about behavior, and the claim is only true if *every*
failure mode that could prevent the enriching call actually reaches that documented value —
not just the one mode a test happened to cover.

This was measured, not theorized: an earlier version of this pattern promised a blank-labels
degradation when no enrichment file was configured. The only path that actually reached it was
a **missing config entry**. An *unreadable* file threw an uncaught exception instead — from a
phase that ran after the primary read had already succeeded — and killed the whole run even
though the source data was already safely fetched.

`_enrich` enumerates the five failure modes that can prevent an optional enrichment merge, and
routes all five to the same degraded return value (the report unchanged):

1. The enrichment path is not configured (`path_labels is None`).
2. The file is absent.
3. The file is malformed.
4. The file cannot be read (permission error).
5. Any other unforeseen failure while reading or applying the file.

Modes 2-5 share one `try/except Exception` around the single call that can raise them — a
per-exception-type `except` clause list would, in practice, cover the one mode that got
tested and silently miss the rest, reproducing the original defect under a different shape.

The second half of the contract is **phase ordering**: `_enrich` runs *before* `_render`
(which persists the report). A phase that can fail must sit before persistence, never after —
otherwise its failure invalidates work that already succeeded and was already durable.

---

## Rules of thumb

- One public service class per file (the ORM model + its `Base` live beside it as mapping declarations).
- The model may import SQLAlchemy; the view never does.
- The controller is the only place that knows about all three layers.

---

## Learn more

- [API Reference](api/index.md) — engine/session factory, model/view usage, and extension patterns

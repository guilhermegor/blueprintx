# **Architecture — MVC Service (Native DB)**

A classical Model–View–Controller layout for script/pipeline-style services. The controller reads top to bottom and wires the other layers; the model owns data access; the view owns output rendering.

This skeleton uses **native database drivers** (sqlite3, psycopg, mysql-connector, pyodbc, oracledb) — the model issues SQL directly and shapes results into pandas DataFrames. For an ORM-backed variant, use the **MVC Service (ORM)** skeleton instead.

---

## Expected layout

```bash
project/
  src/
    controller/
      main.py            # script-style entry-point: config → model → view
    model/
      example_entity.py  # service-style class: SQL in, pandas DataFrame out
    view/
      report_renderer.py # RenderToExcel — DataFrame → .xlsx
    utils/
      __init__.py        # project-specific helpers
      br_identifiers.py  # CNPJ/CPF mask · unmask · validate
      dtypes.py          # apply_dtypes() — explicit column typing on load
    config/
      connection_db.py   # build_connection() — native DB-API connection factory
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
| **Model** | `src/model/` | Data access. One service class per file. May touch the DB. Returns pandas DataFrames (or plain dicts/dataclasses). |
| **View** | `src/view/` | Output rendering only (Excel, JSON, HTML, console). No business logic, no DB. |
| **Controller** | `src/controller/` | Orchestration. Imports model + view + config. `main.py` is the script-style entry-point. |
| **Utils** | `src/utils/` | Project-specific cross-cutting helpers. The BR calendar comes from the `wwdates` dependency (wrapped by `utils.dates`). |
| **Config** | `src/config/` | `startup.py` builds runtime singletons once at import (logger, webhook, paths) from YAML + `.env`. |

---

## Data access

`config/connection_db.build_connection()` reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection. Supported backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — install only the one you use. SQLite is the zero-config default. SQL Server adds `DB_MSSQL_AUTH` (`sql` or `aad` for Azure AD Interactive).

`model/example_entity.ExampleEntity` shows the pattern: take the connection, run SQL via a cursor, and shape the rows into a DataFrame with `pd.DataFrame.from_records`.

---

## Enrichment degradation contract

`controller/_pipeline.PipelineOrchestrator._enrich` is the reference example for a
**documented graceful degradation**.

⚠️ **The split of responsibility is what makes the contract enforceable.** The business logic
— reading the label map and merging it into the report — lives in the model collaborator
`model/label_enricher.LabelEnricher`, per the house rule *"business logic stays in the model;
the orchestrator only wires and sequences"*. `LabelEnricher.enrich` **raises**; it never
degrades. `_enrich` keeps only the sequencing and the degraded result.

That direction is deliberate and not interchangeable: a collaborator that swallowed its own
failures would hand the orchestrator nothing to route, and the documented degradation would
again be reachable from only *some* failure modes — the exact defect this section describes.
One place decides what a failure means, and it is the one whose docstring makes the promise. A degradation documented in a docstring ("returns
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

- One public class per file.
- The model may import the DB driver; the view never does.
- The controller is the only place that knows about all three layers.
- Keep `config/startup.py` import-time side effects idempotent — it is imported once and shared.

---

## Learn more

- [API Reference](api/index.md) — connection factory, model/view usage, and extension patterns

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
| **Utils** | `src/utils/` | Project-specific cross-cutting helpers. The BR calendar comes from the `stpstone` dependency (wrapped by `utils.dates`). |
| **Config** | `src/config/` | `startup.py` builds runtime singletons once at import (logger, webhook, paths) from YAML + `.env`. |

---

## Data access

`config/connection_db.build_connection()` reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection. Supported backends: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — install only the one you use. SQLite is the zero-config default. SQL Server adds `DB_MSSQL_AUTH` (`sql` or `aad` for Azure AD Interactive).

`model/example_entity.ExampleEntity` shows the pattern: take the connection, run SQL via a cursor, and shape the rows into a DataFrame with `pd.DataFrame.from_records`.

---

## Rules of thumb

- One public class per file.
- The model may import the DB driver; the view never does.
- The controller is the only place that knows about all three layers.
- Keep `config/startup.py` import-time side effects idempotent — it is imported once and shared.

---

## Learn more

- [API Reference](api.md) — connection factory, model/view usage, and extension patterns

# **API Reference — MVC Service (Native DB)**

Usage examples for the connection factory, the model/view layers, and extension patterns.

> **See also:** [Architecture](../architecture.md)

---

## Connection factory

`build_connection()` reads `DB_BACKEND` from `.env` and returns a raw DB-API 2.0 connection.

```python
from config.connection_db import build_connection

# .env: DB_BACKEND=sqlite  DB_PATH=./data/app.db
cls_connection = build_connection()
```

Supported values for `DB_BACKEND`: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Non-SQLite backends read `DB_DSN` first; if unset they compose a connection from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`.

---

## Model — SQL in, DataFrame out

```python
from config.connection_db import build_connection
from model.example_entity import ExampleEntity

cls_connection = build_connection()
cls_example = ExampleEntity(cls_connection)
cls_example.ensure_table()
cls_example.insert("Hello")
df_report = cls_example.fetch_all()   # -> pandas DataFrame
cls_connection.close()
```

---

## View — DataFrame to disk

```python
from pathlib import Path
from view.report_renderer import RenderToExcel

RenderToExcel(Path("data/report.xlsx")).render(df_report)
```

Add sibling renderers (JSON, CSV, HTML) in `src/view/` following the same shape: take a DataFrame, write it, return the path.

---

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Adjust the table name, columns, and SQL.
3. Keep DB access inside the model — never in the view.
4. Wire it into `src/controller/main.py`.

One class per file. The view layer must stay free of DB and business logic.

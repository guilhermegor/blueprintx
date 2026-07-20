# **API Reference — MVC Service (ORM)**

Usage examples for the engine/session factories, the model/view layers, and extension patterns.

> **See also:** [Architecture](../architecture.md)

---

## Engine and session factory

`build_engine()` reads `DB_BACKEND` from `.env` and returns a SQLAlchemy `Engine`. `build_session_factory()` returns a bound `sessionmaker`.

```python
from config.connection_db import build_engine, build_session_factory

# .env: DB_BACKEND=sqlite  DB_PATH=./data/app.db
cls_engine = build_engine()
session_factory = build_session_factory(cls_engine)
```

Supported values for `DB_BACKEND`: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Non-SQLite backends read `DB_DSN` first; if unset they compose a URL from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`. Set `SQL_ECHO=true` to log SQL statements.

---

## Model — ORM in, DataFrame out

```python
from config.connection_db import build_engine
from model.example_entity import ExampleEntity

cls_engine = build_engine()
cls_example = ExampleEntity(cls_engine)
cls_example.ensure_table()           # Base.metadata.create_all
cls_example.insert("Hello")          # session.add + commit
df_report = cls_example.fetch_all()  # pd.read_sql(select(...)) -> DataFrame
cls_engine.dispose()
```

---

## View — DataFrame to disk

```python
from pathlib import Path
from view.report_renderer import RenderToExcel

RenderToExcel(Path("data/report.xlsx")).render(df_report)
```

Add sibling renderers (JSON, CSV, HTML) in `src/view/` following the same shape.

---

## Adding a new model entity

1. Copy `src/model/example_entity.py` to `src/model/<entity>.py`.
2. Define the ORM-mapped class (inherit from a shared `Base`) and adjust columns.
3. Keep all DB access in the model — never in the view.
4. Wire it into `src/controller/main.py`.

One public service class per file. The view layer must stay free of DB and business logic.

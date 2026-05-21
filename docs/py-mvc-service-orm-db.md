# **MVC Service (ORM DB)**

A layered **Model–View–Controller** service skeleton for script/pipeline-style Python projects, using the **SQLAlchemy ORM (≥ 2.0)**. The controller reads top-to-bottom and wires the layers; the model declares mapped classes, opens sessions, and shapes query results into pandas DataFrames via `pd.read_sql`; the view renders output. Works with PostgreSQL, MySQL, SQLite, Oracle, and MSSQL.

Shared tooling (Ruff, pre-commit, pytest.ini, GitHub Actions CI, Makefile, `bin/` helpers, VS Code config) comes from `templates/python-common` and is copied verbatim at scaffold time. The `config/` bundle (logger, MS Teams webhook, runtime singletons + YAML) is shared with the DDD skeletons.

---

## 🔑 Key differences vs MVC Service (Native DB)

| Aspect | MVC Native DB | MVC ORM DB |
|--------|---------------|------------|
| Data access | Raw DB-API connection + cursor SQL | SQLAlchemy `Engine` + `sessionmaker` + ORM models |
| Reads | `cursor.fetchall()` → `pd.DataFrame.from_records` | `pd.read_sql(select(...))` |
| Writes | `cursor.execute(INSERT ...)` | `session.add(...)` + `commit()` |
| Dependencies | native drivers (psycopg, pyodbc, …) | `sqlalchemy>=2.0` |
| Schema | hand-written SQL | declarative mapped classes |

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/
    controller/
      main.py            # script-style entry-point: config → model → view
    model/
      conexao_db.py      # build_engine() / build_session_factory() — SQLAlchemy factories
      example_entity.py  # DeclarativeBase + ORM model + service class (Session → DataFrame)
    view/
      report_renderer.py # RenderToExcel — DataFrame → .xlsx
    utils/
      __init__.py        # project-specific helpers; shared utilities come from stpstone
    config/
      startup.py         # logger, MS Teams webhook, runtime constants (singletons)
      inputs.yaml · outputs.yaml · webhooks.yaml · emails.yaml
      signatures/ · queries/
  tests/{unit,integration,performance}/
  bin/                   # shell helpers called by the Makefile
  data/ · assets/ · docs/
  .github/workflows/tests.yaml
  .env · pyproject.toml · ruff.toml · pytest.ini · .pre-commit-config.yaml
```

---

## 📁 Folder descriptions

| Folder | Purpose | Expected content |
|--------|---------|------------------|
| `src/controller/` | Orchestration | `main.py` — script-style pipeline wiring config, model, and view |
| `src/model/` | Data access | ORM models + service classes; `conexao_db.py` engine/session factory; returns DataFrames |
| `src/view/` | Output rendering | Renderers (Excel/JSON/HTML/console) — no DB, no business logic |
| `src/utils/` | Project helpers | Calendars/parsers/dates come from the `stpstone` dependency |
| `src/config/` | Runtime config | `startup.py` singletons + YAML config; secrets in `.env` |
| `tests/{unit,integration,performance}/` | Tests | pytest, mirrors `src/` |
| `bin/` | Shell helpers | Entry-point scripts called by the `Makefile` |

---

## 🧱 Layers

### Model (`src/model`)

**What goes here:** A `DeclarativeBase`, ORM-mapped classes, and a service class that opens sessions for writes and uses `pd.read_sql` for reads.

```python
# model/example_entity.py
class Base(DeclarativeBase): ...

class ExampleRecord(Base):
    __tablename__ = "example"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

class ExampleEntity:
    def __init__(self, cls_engine: Engine) -> None:
        self.cls_engine = cls_engine
        self._session_factory = sessionmaker(bind=cls_engine, expire_on_commit=False)

    def fetch_all(self) -> pd.DataFrame:
        with self.cls_engine.connect() as cls_conn:
            return pd.read_sql(select(ExampleRecord), cls_conn)
```

### View (`src/view`)

**What goes here:** Output rendering only — identical to the native variant. No DB, no business logic.

```python
# view/report_renderer.py
class RenderToExcel:
    def render(self, df_report: pd.DataFrame) -> Path:
        df_report.to_excel(self.path_out, index=False, engine="openpyxl")
        return self.path_out
```

### Controller (`src/controller`)

**What goes here:** Orchestration. Script-style — read top to bottom.

```python
# controller/main.py
from model.conexao_db import build_engine
from model.example_entity import ExampleEntity
from view.report_renderer import RenderToExcel

cls_engine = build_engine()                    # reads DB_BACKEND from .env
cls_example = ExampleEntity(cls_engine)
cls_example.ensure_table()
df_report = cls_example.fetch_all()
RenderToExcel(Path("data/report.xlsx")).render(df_report)
```

---

## 🔄 Session lifecycle

The service class owns the `sessionmaker`. Open a session per write and close it in a `finally`; reads use `pd.read_sql` on an engine connection. Keep `commit()` at the service boundary — never inside a lower-level helper.

---

## 📏 Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Model** | ORM models + data access; returns DataFrames; the only layer importing SQLAlchemy |
| **View** | Output rendering only; no DB, no logic |
| **Controller** | Orchestration; the only layer that knows all three |
| **Config** | Runtime singletons; secrets stay in `.env` |

---

## 🔌 Database backends

`build_engine()` reads `DB_BACKEND` from `.env`. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. SQLite is the zero-config default. Set `SQL_ECHO=true` to log SQL statements.

# **MVC Service (Native DB)**

A layered **Model–View–Controller** service skeleton for script/pipeline-style Python projects, using **native database drivers** (sqlite3, psycopg, mysql-connector, pyodbc, oracledb). The controller reads top-to-bottom and wires the layers; the model owns data access and returns pandas DataFrames; the view renders output. Ideal for data/analytics pipelines that don't need the ceremony of full DDD.

Shared tooling (Ruff, pre-commit, pytest.ini, GitHub Actions CI, Makefile, `bin/` helpers, VS Code config) comes from `templates/python-common` and is copied verbatim at scaffold time. The `config/` bundle (logger, MS Teams webhook, runtime singletons + YAML) is shared with the DDD skeletons.

---

## 🔑 Key differences vs DDD Service (Native DB)

| Aspect | DDD Service (Native DB) | MVC Service (Native DB) |
|--------|-------------------------|-------------------------|
| Structure | Hexagonal: `chassis/` + `capabilities/<feature>/{domain,application,infrastructure}` | Flat MVC: `controller/`, `model/`, `view/` |
| Entry point | `src/main.py` wiring a composition root | `src/controller/main.py` — script-style, top-to-bottom, no `run()` |
| Data access | `DatabaseHandler` ABC + factory + ports | `model/conexao_db.build_connection()` — direct DB-API connection |
| Tests | unittest | pytest |
| Best for | Long-lived services, APIs | Data pipelines, analytics scripts, reports |

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/
    controller/
      main.py            # script-style entry-point: config → model → view
    model/
      conexao_db.py      # build_connection() — native DB-API connection factory
      example_entity.py  # service-style class: SQL in, pandas DataFrame out
    view/
      report_renderer.py # RenderToExcel — DataFrame → .xlsx
    utils/
      __init__.py        # project-specific helpers; the BR calendar comes from stpstone
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
| `src/model/` | Data access | One service class per file; `conexao_db.py` connection factory; returns DataFrames |
| `src/view/` | Output rendering | Renderers (Excel/JSON/HTML/console) — no DB, no business logic |
| `src/utils/` | Project helpers | The BR calendar comes from the `stpstone` dependency (wrapped by `utils.dates`) |
| `src/config/` | Runtime config | `startup.py` singletons + YAML config; secrets in `.env` |
| `tests/{unit,integration,performance}/` | Tests | pytest, mirrors `src/` |
| `bin/` | Shell helpers | Entry-point scripts called by the `Makefile` |

---

## 🧱 Layers

### Model (`src/model`)

**What goes here:** Data access. One service class per file. May touch the DB; returns pandas DataFrames.

```python
# model/example_entity.py — SQL in, DataFrame out
class ExampleEntity:
    def __init__(self, cls_connection, str_table: str = "example") -> None:
        self.cls_connection = cls_connection
        self.str_table = str_table

    def fetch_all(self) -> pd.DataFrame:
        cls_cursor = self.cls_connection.cursor()
        cls_cursor.execute(f"SELECT * FROM {self.str_table}")  # noqa: S608
        list_cols = [col[0] for col in cls_cursor.description]
        return pd.DataFrame.from_records(cls_cursor.fetchall(), columns=list_cols)
```

### View (`src/view`)

**What goes here:** Output rendering only — no DB, no business logic.

```python
# view/report_renderer.py
class RenderToExcel:
    def __init__(self, path_out: Path, str_sheet_name: str = "report") -> None:
        self.path_out = path_out
        self.str_sheet_name = str_sheet_name

    def render(self, df_report: pd.DataFrame) -> Path:
        df_report.to_excel(self.path_out, sheet_name=self.str_sheet_name, index=False, engine="openpyxl")
        return self.path_out
```

### Controller (`src/controller`)

**What goes here:** Orchestration. Script-style — read top to bottom.

```python
# controller/main.py
from config.startup import LOGGER, ENVIRONMENT
from model.conexao_db import build_connection
from model.example_entity import ExampleEntity
from view.report_renderer import RenderToExcel

cls_connection = build_connection()           # reads DB_BACKEND from .env
cls_example = ExampleEntity(cls_connection)
cls_example.ensure_table()
df_report = cls_example.fetch_all()
RenderToExcel(Path("data/report.xlsx")).render(df_report)
```

---

## 📏 Rules of thumb

| Layer | Responsibility |
|-------|----------------|
| **Model** | Data access; returns DataFrames; the only layer that imports a DB driver |
| **View** | Output rendering only; no DB, no logic |
| **Controller** | Orchestration; the only layer that knows all three |
| **Config** | Runtime singletons; secrets stay in `.env` |

---

## 🔌 Database backends

`build_connection()` reads `DB_BACKEND` from `.env`. Supported: `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Drivers are imported lazily — install only the backend you use. SQLite is the zero-config default.

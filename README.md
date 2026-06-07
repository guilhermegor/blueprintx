<!-- markdownlint-disable MD013 -->
# BlueprintX <img src="assets/logo.png" align="right" width="180" style="border-radius: 12px;" alt="BlueprintX logo">

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Bash](https://img.shields.io/badge/bash-%3E%3D4-4EAA25?logo=gnubash&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Open Issues](https://img.shields.io/github/issues/guilhermegor/BlueprintX)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

**BlueprintX** is a lightweight scaffolding tool (Make + bash) for creating ready-to-code projects. It is language-agnostic by design.

## ✨ Highlights
- Interactive CLI (`make new`) with auto-discovered language and skeleton menus
- **Python skeletons**: **DDD service (Native DB)**, **DDD service (ORM DB)** with SQLAlchemy, **MVC service (Native DB)**, **MVC service (ORM DB)**, and **lib-minimal**
- **TypeScript skeletons**: **React SPA (Webpack)** — React 19 + TypeScript + Webpack 5 + Babel + ESLint + Prettier
- Common Python baseline: templated `pyproject.toml`, pre-commit, VS Code settings, CI workflow, CODEOWNERS, PR template, and test folders
- Common TypeScript baseline: `package.json` with pinned deps, `.gitignore`, VS Code settings, `CONTRIBUTING.md`, GitHub Actions CI (type-check + lint + build)
- **Offline git-diff sync**: when you scaffold a project without connecting it to GitHub, BlueprintX adds a `git_diff_export` / `git_diff_check` / `git_diff_apply` workflow for moving changes between machines via patch files (e.g. email) — no GitHub required
- Dev/preview modes: temp scaffolds, dry-run structure previews, optional auto-clean
- **Extensible by design**: drop a `skeleton.meta` file into any `templates/` directory and it appears in the menu automatically

## 📦 Installation

<details>
<summary><strong>Homebrew</strong> (macOS / Linux)</summary>

```bash
brew tap guilhermegor/blueprintx https://github.com/guilhermegor/blueprintx
brew install blueprintx
```

To uninstall:

```bash
brew uninstall blueprintx
brew untap guilhermegor/blueprintx
```

</details>

<details>
<summary><strong>Chocolatey</strong> (Windows)</summary>

Requires [Git for Windows](https://gitforwindows.org/) (provides `bash.exe`).

```powershell
choco install blueprintx
```

To uninstall:

```powershell
choco uninstall blueprintx
```

</details>


<details>
<summary><strong>apt</strong> (Debian / Ubuntu)</summary>

```bash
# One-time: add the repository and signing key
curl -fsSL https://guilhermegor.github.io/blueprintx/apt/gpg.key \
    | sudo gpg --dearmor -o /usr/share/keyrings/blueprintx.gpg

echo "deb [arch=all signed-by=/usr/share/keyrings/blueprintx.gpg] \
    https://guilhermegor.github.io/blueprintx/apt stable main" \
    | sudo tee /etc/apt/sources.list.d/blueprintx.list

sudo apt update
sudo apt install blueprintx
```

To uninstall:

```bash
sudo apt remove blueprintx
sudo rm /etc/apt/sources.list.d/blueprintx.list /usr/share/keyrings/blueprintx.gpg
```

</details>

<details>
<summary><strong>Snap</strong> (Linux)</summary>

```bash
sudo snap install blueprintx --classic
```

To uninstall:

```bash
sudo snap remove blueprintx
```

</details>

<details>
<summary><strong>Git clone</strong> (any platform)</summary>

```bash
git clone https://github.com/guilhermegor/blueprintx.git
cd blueprintx
make new
```

</details>

## 🚀 Usage

### After a package manager installation

The `blueprintx` command is available system-wide:

```bash
blueprintx new          # interactive scaffolder — choose a skeleton and project name
blueprintx preview      # show all available skeleton structures
blueprintx dev          # scaffold into a temp dir (kept after exit)
blueprintx dev-clean    # scaffold into temp dir, auto-deleted on exit
blueprintx dry-run      # print chosen skeleton structure; no files written
blueprintx --help       # show all commands and options
```

### After git clone

The same targets are available via `make` or `./tasks.sh` from the repo root:

```bash
make new          # equivalent to blueprintx new
make preview      # equivalent to blueprintx preview
make dev
make dev-clean
make dry-run
make mkdocs_server  # serve the docs site locally at http://0.0.0.0:8000
```

**Requirements:** `bash` ≥ 4. For Python skeletons, use `pyenv`/`poetry` in the generated project. For TypeScript skeletons, use Node.js ≥ 20 and run `npm install` after scaffolding. On Windows, [Git for Windows](https://gitforwindows.org/) must be installed so that `bash.exe` is on `PATH`.

## 🏗️ Supported skeletons

### DDD service — Native DB (templates/ddd-service-native-db)
Domain-Driven Design service skeleton with hexagonal/ports-and-adapters structure. Uses **native database libraries** (psycopg2, sqlite3, cx_Oracle, pyodbc, pymysql) for direct DB access. `chassis/` holds shared cross-cutting providers; `capabilities/<feature>/` hosts each bounded context's domain, application layer, and adapters.

```
project/
    src/
        chassis/
            db/domain/ports.py            # DatabaseHandler ABC
            db_schema/
                domain/
                infrastructure/           # sqlite, postgres, mariadb, mysql, mssql, oracle
                application/              # build_database_handler() factory
            db_wschema/
                infrastructure/           # json, csv, joblib handlers + SanityCheck
                application/              # build_storage_handler() factory
            typing/                       # ABCTypeCheckerMeta, ProtocolTypeCheckerMeta
        capabilities/
            example_feature/
                domain/                   # entities, DTOs, enums, Protocol ports
                application/              # use-cases, factories
                infrastructure/           # repositories implementing domain ports
        app/
            bootstrap.py                  # env loading, logging, timing
            container.py                  # composition root (AppContainer)
        config/
            startup.py                    # logger, webhooks, runtime constants
        main.py
    tests/{unit,integration,performance}/
    container/
    bin/
    assets/
    docs/
    .github/
    .vscode/
    .env
    pyproject.toml
    requirements.txt
    README.md
```

### DDD service — ORM DB (templates/ddd-service-orm-db)
Same DDD hexagonal structure, but uses **SQLAlchemy ORM (≥ 2.0)** for database operations. Works with PostgreSQL, MySQL, SQLite, Oracle, and MSSQL through a unified `DatabaseSession` / `Repository` ABC.

```
project/
    src/
        chassis/
            db_schema/
                domain/
                infrastructure/
                    base.py          # Base (DeclarativeBase) + DatabaseSession + Repository ABC
                    models.py        # ORM models
                    repository.py    # SQLAlchemyRecordRepository (generic reference impl)
                application/         # build_database_session() factory
            typing/
        capabilities/
            example_feature/
                domain/
                application/
                infrastructure/
        app/
        config/
        main.py
    tests/{unit,integration,performance}/
    ... (same structure as native-db)
```

### MVC service — Native DB (templates/mvc-service-native-db)
Layered **Model–View–Controller** skeleton for script/pipeline-style projects, using **native database drivers** (sqlite3, psycopg, mysql-connector, pyodbc, oracledb). The controller (`src/controller/main.py`) is a script-style, top-to-bottom pipeline that wires config → model → view. The model returns pandas DataFrames; the view renders them (e.g. `RenderToExcel`). Flatter than DDD — ideal for data/analytics pipelines and reports. Tests use pytest.

```
project/
    src/
        controller/main.py    # script-style entry-point: config → model → view
        model/
            conexao_db.py     # build_connection() — native DB-API connection factory
            example_entity.py # service-style class: SQL in, pandas DataFrame out
        view/report_renderer.py  # RenderToExcel — DataFrame → .xlsx
        utils/                # project helpers (calendars/parsers come from stpstone)
        config/               # startup.py singletons + YAML (shared with DDD skeletons)
    tests/{unit,integration,performance}/
    bin/ · data/ · assets/ · docs/
    .env · pyproject.toml · ruff.toml · pytest.ini
```

### MVC service — ORM DB (templates/mvc-service-orm-db)
Same flat MVC structure, but the model uses the **SQLAlchemy ORM (≥ 2.0)** — `build_engine()` / `build_session_factory()`, declarative models, and `pd.read_sql` reads. Works with PostgreSQL, MySQL, SQLite, Oracle, and MSSQL.

```
project/
    src/
        controller/main.py
        model/
            conexao_db.py     # build_engine() / build_session_factory()
            example_entity.py # DeclarativeBase + ORM model + service class
        view/report_renderer.py
        utils/ · config/
    tests/{unit,integration,performance}/
    ... (same structure as native-db)
```

### lib-minimal
Lean library starter: package under `src/<project_name>/`, tests, CI, VS Code config, and pre-commit ready to go.

```
project/
    src/<project_name>/
    tests/{unit,integration,performance}/
    docs/
    container/
    bin/
    .github/
    .vscode/
    .env
    pyproject.toml
    README.md
```

### React SPA — Webpack (templates/react-spa-webpack)
Full-stack SPA skeleton using **React 19**, **TypeScript 6**, **Webpack 5**, and **Babel**, structured around **hexagonal / DDD principles**. Each business capability lives in `src/capabilities/<name>/` with isolated `domain/`, `application/`, `infrastructure/`, and `ui/` layers. Layer boundaries are enforced at lint time via `eslint-plugin-boundaries`. At scaffold time you choose a **state management strategy** (React Context, Zustand, or Redux Toolkit) — only the chosen variant's files are written.

```
project/
    src/
        App.tsx                          # wires capability providers
        index.tsx                        # entry point
        declarations.d.ts               # CSS module type declarations
        capabilities/
            <feature>/
                domain/                  # DTOs, entities, enums, port interfaces
                application/             # use-case hooks, DTO↔entity assemblers
                infrastructure/          # API adapters implementing domain ports
                ui/                      # components, pages, CSS Modules
                context.tsx              # composition root (wires infra into app)
                index.ts                 # public barrel
        routes/
        shared/                          # cross-cutting styles, components, utils
    public/
        index.html
    .babelrc
    eslint.config.js
    .prettierrc.js
    tsconfig.json
    webpack.config.js
    package.json
    .gitignore
    .vscode/
    docs/
    .github/
        workflows/
            ci.yml                       # type-check, lint, build
    CONTRIBUTING.md
    LICENSE
```

After scaffolding, run `npm install && npm start` to launch the dev server on `http://localhost:3000`.

## 🔁 Offline git-diff sync

When you scaffold a project and **decline** connecting it to a GitHub remote, BlueprintX adds a small offline-sync workflow so you can move changes between machines as patch files (e.g. attach to an email) — useful in restricted/air-gapped environments. It is **only** added in this no-GitHub case; projects pushed to GitHub stay clean.

| Command (Python: `make` / TypeScript: `npm run`) | Action |
|---------------------------------------------------|--------|
| `git_diff_export` (`git:diff:export`) | Export commits in `DIFF_RANGE` (default `main..HEAD`) to a dated `git_diffs/<branch>_<timestamp>.diff` |
| `git_diff_check FILE=<path>` (`git:diff:check`) | Check whether a `.diff` applies cleanly — no changes made |
| `git_diff_apply FILE=<path>` (`git:diff:apply`) | Apply a `.diff` to the working tree (does **not** stage or commit — you review and commit yourself) |

Cross-platform (Windows Git Bash, macOS, Linux); the scripts live in `bin/` and source a shared `bin/lib/common.sh` status helper.

## 🧭 Folder attribution (ddd-service templates)
- `chassis/`: shared cross-cutting providers (DB handlers, storage, type enforcement).
- `chassis/db/`: `DatabaseHandler` ABC — contract all backends implement.
- `chassis/db_schema/`: SQL-backed handlers + `build_database_handler()` factory.
- `chassis/db_wschema/`: schema-less handlers (JSON, CSV, joblib) + `build_storage_handler()`.
- `chassis/typing/`: runtime type enforcement (`ABCTypeCheckerMeta`, `ProtocolTypeCheckerMeta`).
- `capabilities/<feature>/domain/`: feature entities, DTOs, enums, `Protocol` ports.
- `capabilities/<feature>/application/`: use-case orchestration; no I/O or framework code.
- `capabilities/<feature>/infrastructure/`: adapters implementing domain ports.
- `app/`: `bootstrap.py` (env/logging) + `container.py` (composition root).
- `config/`: module-level singletons and YAML config; secrets stay in `.env`.

## 📂 Repo layout (this tool)

```
BlueprintX/
├── Makefile                 # entry targets: new, preview, dev, dev-clean, dry-run
├── tasks.sh                 # same targets for non-make usage
├── bin/
│   ├── blueprintx.sh        # interactive menu + auto-discovery
│   ├── preview.sh           # skeleton previews
│   ├── help.sh              # usage tips and targets
│   ├── venv.sh              # convenience venv bootstrap
│   └── scaffold/            # per-skeleton scaffolders
│       ├── python_ddd_service.sh      # DDD native DB scaffold
│       ├── python_ddd_service_orm.sh  # DDD SQLAlchemy ORM scaffold
│       ├── python_mvc_service.sh      # MVC native DB scaffold
│       ├── python_mvc_service_orm.sh  # MVC SQLAlchemy ORM scaffold
│       ├── python_lib_minimal.sh      # lib-minimal scaffold
│       └── ts_react_app.sh            # React SPA (Webpack) scaffold
├── templates/               # skeleton contents + discovery metadata
│   ├── common/                 # language-agnostic shared assets (CODEOWNERS, PR template,
│   │   │                       #   bin/ git-diff scripts + lib/common.sh, make/git_diff.mk)
│   │   ├── bin/
│   │   └── make/
│   ├── python-common/          # shared assets for all Python skeletons
│   ├── ts-common/              # shared assets for all TypeScript skeletons
│   ├── ddd-service-native-db/  # DDD/hexagonal with native DB libraries
│   │   └── skeleton.meta
│   ├── ddd-service-orm-db/     # DDD/hexagonal with SQLAlchemy ORM
│   │   └── skeleton.meta
│   ├── mvc-service-native-db/  # layered MVC with native DB drivers
│   │   └── skeleton.meta
│   ├── mvc-service-orm-db/     # layered MVC with SQLAlchemy ORM
│   │   └── skeleton.meta
│   ├── lib-minimal/            # minimal library template
│   │   └── skeleton.meta
│   ├── react-spa-webpack/      # React 19 + TypeScript + Webpack 5 SPA
│   │   └── skeleton.meta
│   └── licenses/               # license text files
├── docs/                    # mkdocs sources
├── mkdocs.yml               # mkdocs config
└── assets/logo.png          # logo used in this README
```

## 👨‍💻 Authors

**Guilherme Rodrigues**  
[![GitHub](https://img.shields.io/badge/GitHub-guilhermegor-181717?style=flat&logo=github)](https://github.com/guilhermegor)  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Guilherme_Rodrigues-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/guilhermegor/)

## 🔗 Useful Links

* [GitHub Repository](https://github.com/guilhermegor/BlueprintX)

* [Issue Tracker](https://github.com/guilhermegor/BlueprintX/issues)

## 🤝 Contributing
Issues and PRs are welcome. Please keep templates minimal, opinionated, and consistent across skeletons.

## 📜 License
MIT. See [LICENSE](LICENSE).

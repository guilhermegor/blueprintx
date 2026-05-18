# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

BlueprintX is a **Make + bash scaffolding tool** — not a Python application. The root `pyproject.toml` exists only to drive the MkDocs documentation site. All Python code lives inside `templates/` and is copied verbatim into scaffolded projects.

## Commands

### Scaffolding (primary usage)
```bash
make new           # interactive scaffolder — prompts for language, skeleton, project name
make preview       # show all skeleton structures without creating anything
make dev           # scaffold into a temp dir (preserved)
make dev-clean     # scaffold into temp dir, auto-deleted on exit
make dry-run       # print chosen skeleton structure; no files written
```

### Docs site (MkDocs)
```bash
make mkdocs_server  # installs docs deps then serves at http://0.0.0.0:8000
```

### Dev environment (root project)
```bash
make init_venv     # run bin/init_venv.sh to bootstrap poetry venv
make update_venv   # poetry update
```

### Generated project commands (inside a scaffolded project)
Once a project is created the template Makefile provides:
```bash
make init_venv     # bootstrap poetry venv
make vscode_init   # install VS Code extensions + keybindings
make export_deps   # export poetry deps to requirements.txt via pre-commit hook
poetry run python -m unittest discover -s tests/unit -p "*.py" -v
poetry run python -m unittest discover -s tests/integration -p "*.py" -v
```

## Repo architecture

```
BlueprintX/
├── Makefile                        # top-level entry points
├── tasks.sh                        # same targets for non-make usage
├── bin/
│   ├── blueprintx.sh               # interactive menu + mode parsing (--dev, --dry-run, --clean)
│   ├── preview.sh                  # skeleton structure previews
│   ├── help.sh                     # usage tips
│   ├── init_venv.sh                # venv bootstrap for this repo
│   └── scaffold/
│       ├── python_ddd_service.sh      # native-DB scaffold logic
│       ├── python_ddd_service_orm.sh  # SQLAlchemy ORM scaffold logic
│       ├── python_lib_minimal.sh      # lib-minimal scaffold logic
│       └── ts_react_app.sh            # React SPA (Webpack) scaffold logic
├── templates/
│   ├── python-common/              # shared assets copied into ALL Python skeletons
│   ├── ts-common/                  # shared assets copied into ALL TypeScript skeletons
│   ├── ddd-service-native-db/      # DDD skeleton with native DB drivers
│   │   └── skeleton.meta           # discovery descriptor (language, display_name, scaffold)
│   ├── ddd-service-orm-db/         # DDD skeleton with SQLAlchemy ORM
│   │   └── skeleton.meta
│   ├── lib-minimal/                # minimal library skeleton
│   │   └── skeleton.meta
│   ├── react-spa-webpack/          # React 19 + TypeScript + Webpack 5 SPA skeleton
│   │   └── skeleton.meta
│   └── licenses/                   # license text files (MIT, Apache-2.0, GPL-3.0, …)
├── docs/                           # MkDocs source pages
└── mkdocs.yml
```

## Discovery system

`bin/blueprintx.sh` builds the language and skeleton menus at runtime by scanning every `templates/*/skeleton.meta` file. A `skeleton.meta` is a shell-sourceable KEY=VALUE file with four fields:

```
language=<python|typescript|…>
display_name=<Human-readable name shown in the menu>
description=<One-line description shown in previews>
scaffold=<relative path from repo root, e.g. bin/scaffold/ts_react_app.sh>
```

- `prompt_language` de-duplicates `language=` values across all discovered metas.
- `prompt_skeleton` shows only skeletons whose `language=` matches the user's choice.
- `create_project` reads `scaffold=` from the matched meta and delegates to that script.
- Directories without `skeleton.meta` (`python-common`, `ts-common`, `licenses`) are ignored.

To add a new skeleton: create its directory under `templates/`, add a `skeleton.meta`, write a scaffold script under `bin/scaffold/`, and the menu updates automatically — no changes to `blueprintx.sh` required.

## How scaffolding works

### Python skeletons (`python_ddd_service.sh`, `python_ddd_service_orm.sh`, `python_lib_minimal.sh`)

1. `validate_inputs` — checks required args.
2. `resolve_github_username` — env var → `gh` CLI → interactive prompt.
3. `create_directory_structure` — `mkdir -p` for the target layout.
4. `create_python_files` — copies `templates/ddd-service-*/src/` into the project.
5. `copy_templates` — copies project-specific files (`.env`, README, etc.).
6. `copy_common_templates` — `envsubst` renders `pyproject.toml`, then copies everything from `templates/python-common/` (ruff.toml, pre-commit config, Makefile, CI workflow, etc.).
7. `prompt_git_remote_setup` — optionally initialises git, creates GitHub repo via `gh`, and applies branch protection.

### TypeScript skeletons (`ts_react_app.sh`)

1. `validate_inputs` — checks required args.
2. `resolve_github_username` — env var → `gh` CLI → interactive prompt.
3. `create_directory_structure` — `mkdir -p` for the target layout.
4. `copy_skeleton_files` — copies `templates/react-spa-webpack/` verbatim.
5. `copy_common_templates` — `envsubst` renders `ts-common/package.json`; copies `.gitignore`, `.vscode/settings.json`, `CONTRIBUTING.md`, license file.
6. `prompt_git_remote_setup` — optionally initialises git, creates GitHub repo via `gh`, and applies branch protection.

The `templates/python-common/` directory is the **single source of truth** for shared Python tooling. The `templates/ts-common/` directory is the **single source of truth** for shared TypeScript tooling. Changes to either propagate to all skeletons of that language on the next scaffold run.

## Template Python conventions (must be respected in all template files)

- **Ruff** is the linter/formatter. Config lives in `templates/python-common/ruff.toml`: line-length 99, tab indent, double quotes, NumPy docstrings.
- **Pre-commit hooks** (`.pre-commit-config.yaml`): ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests** use `unittest` (not pytest) and are discovered with `python -m unittest discover`.
- **One class per file**. Ports (ABCs) in `domain/ports.py`, ORM/DB implementations in `infrastructure/`, orchestration in `application/use_cases.py`. Never mix layers in one file.
- `pyproject.toml` in templates uses `${VARIABLE}` placeholders — these are resolved via `envsubst` at scaffold time; do not replace them with literal values.
- **Type-prefix naming** — every variable name starts with a type prefix to make the type visible without inspecting annotations. Never use bare names or underscore prefixes.

  | Prefix | Type | Prefix | Type |
  |--------|------|--------|------|
  | `cls_` | class instance | `list_` | `list` |
  | `float_` | `float` | `tuple_` | `tuple` |
  | `decimal_` | `Decimal` | `dict_` | `dict` (parsed) |
  | `int_` | `int` | `json_` | raw JSON string |
  | `str_` | `str` | `df_` | `pd.DataFrame` |
  | `bool_` | `bool` (or `is_`/`has_`/`can_`) | `series_` | `pd.Series` |
  | `dt_` | `datetime`/`date` | `arr_` | `np.ndarray` |
  | `path_` | `pathlib.Path` | `bytes_` | `bytes` |
  | `fn_` | `Callable` (standalone vars only — not class methods/attrs) | `re_` | `re.Pattern` |

## Hexagonal / DDD layer boundaries (ddd-service skeletons)

| Layer | Location | Allowed dependencies |
|-------|----------|----------------------|
| Domain | `capabilities/<feature>/domain/` | Nothing (pure Python, no I/O) |
| Application | `capabilities/<feature>/application/` | Domain only |
| Infrastructure | `capabilities/<feature>/infrastructure/` | Domain ports + external libs |
| Chassis | `src/chassis/` | Cross-cutting providers (db, db_schema, db_wschema, …) |

`chassis/db/domain/ports.py` defines `DatabaseHandler` (ABC) — all DB handlers extend it and implement `create / read / update / delete / backup / close`. SQL backends live in `chassis/db_schema/`, schema-less backends (JSON, CSV, joblib) in `chassis/db_wschema/`.

## File naming conventions

Output files (exports, backups, model artifacts, reports):

```
name-like-this_YYYYMMDD_HHMMSS.<ext>
```

- Name part: kebab-case (dashes, no underscores)
- Separator before timestamp: single `_`
- Timestamp: `YYYYMMDD_HHMMSS` (uppercase, sortable)
- Extension: lowercase

Exception for joblib binary artifacts with integrity checking: `name-like-this_YYYYMMDD_HHMMSS_{sha256_prefix8}.joblib` — the SHA256 suffix is added for security purposes only.

## Branch and commit conventions

From `CONTRIBUTING.md`:
- Branch names: `feat/<name>`, `fix/<desc>`, `docs/<desc>`, `refactor/<desc>`, `chore/<desc>`, `hotfix/<desc>`, `release/<version>`
- Commits: Conventional Commits — `feat(scope): message`, `fix(scope): message`, etc.
- Direct commits to `main` are blocked by pre-commit (`no-commit-to-branch`).

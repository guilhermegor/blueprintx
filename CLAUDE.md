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
make init          # bootstrap venv + install pre-commit hooks (venv + precommit)
make venv          # run bin/venv.sh to bootstrap poetry venv
make precommit     # install pre-commit + commit-msg hooks
make lint          # run all pre-commit hooks across the repo (mirrors CI)
make update_venv   # poetry update
```

The root repo has its **own** pre-commit (`/.pre-commit-config.yaml`) that mirrors
`.github/workflows/scaffold_checks.yml`: the shared checks live in `bin/ci/*.sh`
(`check_spelling.sh`, `check_shell.sh`, `check_docs_build.sh`, `validate_meta.sh`,
`check_version_sync.sh`, `check_codespell_sync.sh`, `check_actions.sh`) and **both** the
workflow and the hook call them — one home per check, zero drift. This is distinct from the
scaffolded-project pre-commit shipped in `templates/python-common/`.

Two of those exist because a defect can only be seen from *this* side of the copy:

- `check_codespell_sync.sh` — the root `.codespellrc` and `templates/python-common/.codespellrc`
  must carry the same `ignore-words-list`. They drifted in **both** directions (30 words one
  way, 25 the other) and the stale copy was the **template**, so the cost landed only on
  generated projects, which re-learned each word one rejected commit at a time. ⚠️ Write every
  entry **lowercase**: codespell lowercases the found word before lookup, so a lowercase entry
  covers every casing while a capitalised one matches only itself.
- `check_actions.sh` — actionlint over this repo's workflows **and** the ones inside
  `templates/`. Template workflows never execute here, so nothing exercised them: the gate's
  first run found 8 real defects, including `actions/cache@v3` (a version GitHub no longer
  runs) in three tiers. Resolves gracefully when actionlint is absent; CI sets
  `LINT_ACTIONS_REQUIRED=1`, because a skip in CI is a gate reporting its own blindness as OK.
  It also runs `check_job_timeouts` over the same discovered set — every job with `runs-on:`
  must carry `timeout-minutes:`. That check needs no external tool, so it deliberately runs
  **before** the actionlint resolve and never inherits its graceful skip. GitHub's default
  bound is 6 hours, and an unbounded job that hangs reports `cancelled` — indistinguishable
  from a human pressing cancel (measured twice in two days, #192).

The **cyclomatic-complexity gate** follows the same one-implementation rule:
`templates/python-common/bin/check_complexity.sh`, run over this repo via `--root .`
(pre-commit hook `check-complexity`, the `complexity` CI job) and over itself inside every
generated project. Its ceiling **differs by tree** — 1 for `tests/`, 2 for `src/`, 8 for
`bin/` — because the argument differs: a test with a branch tests two paths and the green
never says which ran, while the gates in `bin/` are parsing tools by nature (at 2 they were
74% violating, a number nobody pays and therefore a gate nobody keeps). It does **not**
reimplement mccabe; ruff already ships it as `C901`, and a hand-rolled counter that treats
`assert`/`with` as decision points reports 85% of `tests/` violating where the real figure is
8%. ⚠️ BlueprintX's own tree has no `src/` or `tests/`, so on this side it checks `bin/`
only — it travels with the template it polices rather than earning its keep from what it
finds here.

The **function-length gate** is wired on both sides but has only ONE implementation:
`templates/python-common/bin/check_function_length.py`, which BlueprintX runs over its own
tree via `--root .` (pre-commit hook `function-length`, the `function-length` CI job,
`make check_function_length` here; `poe check_function_length` in a generated project) and which every generated
project runs on itself. A second copy was the obvious shape and is exactly what
`check_codespell_sync.sh` exists to police, so there is not one.

The **direct-dependency gate** (`templates/python-common/bin/lint_deps.sh`, deptry) is the one
that deliberately does **not** run on this side. It needs an installed environment to map a
module back to its distribution, and BlueprintX has no `src/` and no runtime dependencies — so
here it would have nothing to read and would report success for having checked nothing, the
exact failure the gate family exists to prevent. Its verification is
`bin/ci/scaffold_lint_test.sh`, which runs it inside a real generated project. ⚠️ Its config is
per-tier in each `pyproject.toml` and **cannot** be single-sourced into a shared `deptry.toml`:
`--config <file>` re-points deptry at that file as the *manifest* as well, so it stops reading
the tier's dependency table. That is the one-implementation rule losing to a measured
constraint, which is why the reason is written into all five manifests rather than remembered.

The **review-thread gate** follows the same rule, reached from the other direction: it *did* have
two 543-line copies, and `.github/workflows/review_threads.yml` now runs the shared
`templates/common/bin/check_review_threads.py` directly. It needs no `--root` — unlike the
filesystem gates it takes its subject from `GITHUB_REPOSITORY`/`PR_NUMBER` and reads
`.review-bots.yaml` from `Path.cwd()`, so invoking the shared copy from the repo root already
audits *this* repo's roster. There is deliberately no third copy of the roster either: the one in
`templates/python-common/` is the shipped Python template, the one at the root is this repo's own
data. ⚠️ **The script lives in `templates/common/`, not `templates/python-common/`, on purpose
(blueprintx#175)** — it is the one surface both the Python and TypeScript template families
already copy from, and every `bin/scaffold/python_*.sh` / `ts_*.sh` script copies it into the
generated project's own `bin/` at scaffold time. An earlier `ts-*` revision fetched it over the
network from BlueprintX at CI run time instead; rejected on review as unpinned remote code
executed on a runner holding `GITHUB_TOKEN` — the same hazard the actionlint SHA-256 check below
exists to prevent, applied to a security-relevant gate whose silent corruption (always exit 0)
would be invisible.

`bin/ci/scaffold_lint_test.sh <tier>` is the real verification for template work — it scaffolds
a project and runs **that project's** `make lint`, `make unit_tests` and `make integration_tests`.
Checking at the template root is a false green: the generated project pins different linter
versions. The integration suite matters specifically because it is the only place a `bin/*.sh`
seam is actually executed.

The **Makefile ↔ tasks.sh ↔ help.sh pairing** is enforced by `bin/check_makefile_pairing.sh`
(pre-commit hook `makefile-pairing`, the `makefile-pairing` CI job), not by prose (#241).
Every user-facing `Makefile` target must have a matching `case` branch in `tasks.sh` — the
non-`make` entry point — **and** be listed in `bin/help.sh`'s usage text; a target satisfying
only two of the three legs is exactly the drift this rule exists to prevent (`update_licenses`
was a real, working `Makefile` target missing from `help.sh` until this gate found and fixed
it — undetected by prose, and found only by accident before). "Paired" means name-equality
(with `-`/`_` normalised, since `tasks.sh` legitimately spells `dev-clean` as `dev_clean` in
its `case` pattern) — a target preceded by a `# pairing:internal` comment line is exempt, for
a future `.PHONY` helper that composes other targets but was never meant to be user-facing on
its own. This pair is **root-repo-only**: unlike the rest of the gate family, `Makefile` and
`tasks.sh` exist only at BlueprintX's own root, never in `templates/` and never in a generated
project (`poe_tasks.toml` replaced them there since #236) — so the script lives at
`bin/check_makefile_pairing.sh`, not `templates/python-common/bin/`, and never ships as part
of a scaffold.

### Releasing / version bump
**The version is the git tag — there is no hand-bump.** Cut a release from the **`Release`
GitHub Action** (`release.yml`, `workflow_dispatch` → `version` field): the `tag` job pushes
`vX.Y.Z` and the package-manager jobs stamp that version into each artifact. You enter the version
**once**, in the Action's field — no `make bump_version`, no commit to `main`.

`blueprintx --version` resolves the version at runtime (mirrors how a Python wheel gets its version
from the tag, one layer down):
- **From a git checkout** → `git describe --tags` (a clone always reports the latest tag; nothing
  to bump).
- **From a packaged install** (Homebrew/Chocolatey/Snap/apt) or **`make install`** → no `.git`, so
  it reads the `BLUEPRINTX_VERSION` literal that the install path **stamps from the tag** (the
  `install` recipe seds it; each `release_*.yml` stamps it into its artifact).

In-repo, both `pyproject.toml` (`version = "0.0.0"`, docs-only) and `BLUEPRINTX_VERSION` stay at the
`"0.0.0"` stub — `bin/ci/check_version_sync.sh` enforces this and rejects an accidental hand-bump.
Do not edit either by hand.

### Generated project commands (inside a scaffolded project)
Once a project is created the template Makefile provides:
```bash
make init_venv     # bootstrap poetry venv
make vscode_init   # install VS Code extensions + keybindings
make export_deps   # export locked deps to requirements-lock.txt (pip-only hosts)
make export_context # flatten the repo into repo_context.txt for pasting into a web-UI LLM
poetry run pytest tests/unit/
poetry run pytest tests/integration/
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
│   ├── venv.sh                     # venv bootstrap for this repo
│   └── scaffold/
│       ├── python_ddd_service.sh      # DDD native-DB scaffold logic
│       ├── python_ddd_service_orm.sh  # DDD SQLAlchemy ORM scaffold logic
│       ├── python_mvc_service.sh      # MVC native-DB scaffold logic
│       ├── python_mvc_service_orm.sh  # MVC SQLAlchemy ORM scaffold logic
│       ├── python_lib_minimal.sh      # lib-minimal scaffold logic
│       ├── ts_react_app.sh            # React SPA (Webpack) scaffold logic
│       └── ts_react_capability.sh     # helper: add a capability to an existing React SPA
├── templates/
│   ├── common/                     # language-agnostic assets copied into EVERY skeleton
│   │                               #   (CODEOWNERS, PR template, bin/ git-diff scripts + export_repo_content.sh + lib/common.sh, make/git_diff.mk)
│   ├── python-common/              # shared assets copied into ALL Python skeletons
│   ├── ts-common/                  # shared assets copied into ALL TypeScript skeletons
│   ├── ddd-service-native-db/      # DDD skeleton with native DB drivers
│   │   └── skeleton.meta           # discovery descriptor (language, display_name, scaffold)
│   ├── ddd-service-orm-db/         # DDD skeleton with SQLAlchemy ORM
│   │   └── skeleton.meta
│   ├── mvc-service-native-db/      # layered MVC skeleton with native DB drivers
│   │   └── skeleton.meta
│   ├── mvc-service-orm-db/         # layered MVC skeleton with SQLAlchemy ORM
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
- Directories without `skeleton.meta` (`common`, `python-common`, `ts-common`, `licenses`) are ignored.

To add a new skeleton: create its directory under `templates/`, add a `skeleton.meta`, write a scaffold script under `bin/scaffold/`, and the menu updates automatically — no changes to `blueprintx.sh` required.

## How scaffolding works

### Python skeletons (`python_ddd_service.sh`, `python_ddd_service_orm.sh`, `python_mvc_service.sh`, `python_mvc_service_orm.sh`, `python_lib_minimal.sh`)

1. `validate_inputs` — checks required args.
2. `resolve_github_username` — env var → `gh` CLI → interactive prompt.
3. `create_directory_structure` — `mkdir -p` for the target layout (hexagonal `chassis/`+`capabilities/` for DDD; flat `controller/model/view` for MVC).
4. `create_python_files` — copies the skeleton's `src/` into the project.
5. `copy_templates` — copies project-specific files (`.env`, README, etc.).
6. `copy_common_templates` — `envsubst` renders `pyproject.toml`, then copies everything from `templates/python-common/` (ruff.toml, pre-commit config, Makefile, CI workflow, etc.).
7. `prompt_git_remote_setup` — optionally initialises git, creates GitHub repo via `gh`, and applies branch protection.
8. `apply_offline_mode` — when the user **declines** a GitHub remote, GitHub-only assets are skipped and the offline git-diff workflow (`bin/git_diff_*.sh` + `make/git_diff.mk`) is copied from `templates/common/` instead.

### TypeScript skeletons (`ts_react_app.sh`)

1. `validate_inputs` — checks required args.
2. `resolve_github_username` — env var → `gh` CLI → interactive prompt.
3. `create_directory_structure` — `mkdir -p` for the target layout.
4. `copy_skeleton_files` — copies `templates/react-spa-webpack/` verbatim, and seeds both `.env` (working copy, git-ignored) and `.env.example` (committed template) from the skeleton's `.env.example`.
5. `copy_common_templates` — `envsubst` renders `ts-common/package.json`; copies `.gitignore`, `.vscode/settings.json`, `CONTRIBUTING.md`, license file.
6. `prompt_git_remote_setup` — optionally initialises git, creates GitHub repo via `gh`, and applies branch protection.
7. `apply_offline_mode` — same offline git-diff fallback as the Python skeletons when no GitHub remote is connected.

`bin/scaffold/ts_react_capability.sh` is a standalone helper (not a skeleton): run it against an existing React SPA to scaffold a new `src/capabilities/<name>/` with its `domain/application/infrastructure/ui` layers wired in.

The `templates/python-common/` directory is the **single source of truth** for shared Python tooling. The `templates/ts-common/` directory is the **single source of truth** for shared TypeScript tooling, and `templates/common/` for language-agnostic assets (CODEOWNERS, PR template, offline git-diff workflow). Changes to any of them propagate to all relevant skeletons on the next scaffold run.

## Template Python conventions (must be respected in all template files)

- **Ruff** is the linter/formatter. Config lives in `templates/python-common/ruff.toml`: line-length 99, tab indent, double quotes, NumPy docstrings.
- **Pre-commit hooks** (`.pre-commit-config.yaml`): ruff, pydocstyle (DAR/D412/D417), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge.
- **Tests**: every skeleton runs `pytest` (`make unit_tests` → `poetry run pytest tests/unit/`; `pytest.ini` is shipped from `templates/python-common/` to all tiers). Tests are pytest-style — plain functions with fixtures (`conftest.py`, `capsys`, `monkeypatch`, `pytest_mock`) — not `unittest.TestCase`. Write new tests as pytest functions regardless of tier.
- **One class per file**. Ports (ABCs) in `domain/ports.py`, ORM/DB implementations in `infrastructure/`, orchestration in `application/use_cases.py`. Never mix layers in one file.
- **Explicit column typing on load** — every DataFrame or SQL-to-memory load must declare its column types via a dtype dict passed to `apply_dtypes` (`templates/python-common/src/utils/dtypes.py`), never relying on pandas' inference. `apply_dtypes` also accepts optional `list_date_cols` / `list_datetime_cols`. This applies across every layout (capabilities/model/view).
- **Brazilian identifiers** — CNPJ/CPF formatting goes through `templates/python-common/src/utils/br_identifiers.py` (`mask_*`, `unmask_*`, `is_valid_*`); the CNPJ helpers are alphanumeric-aware for the 2026 format.
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

## Backlog discipline (persist progress to `docs/backlog/`)

Any multi-step effort here (a backport wave, a multi-PR feature) MUST be tracked in a
**`docs/backlog/<topic>_YYYYMMDD_HHMMSS.md`** file, created the moment the plan is approved
and updated after every slice (tick done items, add new to-dos, remove superseded ones).
This is **not optional and not replaced by a session task tool** (TaskCreate/TodoWrite are
session-local; the backlog is the in-repo, team-reviewable, cross-session record). At the
start of work, **re-read any existing `docs/backlog/` file** and keep it current. The
filename timestamp is set at creation and never renamed. `docs/backlog/` is git-ignored from
the published site (`exclude_docs` in each skeleton's `mkdocs.yml`) but tracked in the repo.
**Do NOT delete a backlog file once every box is `[x]`** — keep it as a permanent,
team-reviewable record of what was done and why. When complete, tick the last box and add a
short "Completed — kept as a record" note instead of removing the file. (Lesson:
persist-todo-in-docs-backlog.)

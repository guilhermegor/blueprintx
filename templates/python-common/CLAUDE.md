# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`templates/python-common/` is the **single source of truth for shared tooling** across all BlueprintX Python skeletons. Every file here is copied verbatim (or rendered via `envsubst`) into scaffolded projects by each `bin/scaffold/python_*.sh` script.

**Changes here propagate to all Python skeletons on the next scaffold run.**

Most of this directory is *tooling* (ruff, pytest, Makefile, bin scripts). Two subtrees are the **deliberate exceptions** — they hold *application code* that is identical across skeletons, so it lives here rather than being duplicated:

- **`src/config/`** — the global runtime config (`startup.py`, `inputs.yaml`, `outputs.yaml`). **Always** copied into every service project's `src/config/`. This is why the four service skeletons no longer carry their own `startup.py`/`inputs.yaml`/`outputs.yaml`.
- **`src/utils/`** — project-agnostic helpers (`br_identifiers.py`, `dtypes.py`, `decimals.py`, `loggers.py`, `text.py`, `paths.py`, `signatures.py`, `dates.py`) plus their unit tests. **Always** copied into every service project's `src/utils/` and `tests/unit/`, so the helpers exist in every Python skeleton from one source. These helpers are deliberately decoupled from the `typing` engine (no `@type_checker` import) so they stay portable across the `chassis.typing` (DDD) and `utils.typing` (MVC) layouts.
- **`optional/`** — opt-in app code injected when the matching scaffold prompt is answered *yes* (or, for `typing`, always). Shipped into the generated project's normal layout, so the output looks standard — the `optional/` marker exists only here, to keep the tooling-vs-app-code boundary visible. Contains `webhook/` (opt-in port-based notifier), `chassis/` (opt-in storage), and `typing/` (the runtime type-checking engine — copied to `src/chassis/typing/` for DDD, `src/utils/typing/` for MVC via a `chassis.typing → utils.typing` rewrite, mirroring the webhook seam).

## Files and their roles

| File / Path | Role |
|-------------|------|
| `ruff.toml` | Ruff lint + format config (line-length 99, tab indent, double quotes, NumPy docstrings, full rule set) |
| `.pre-commit-config.yaml` | Hooks: ruff, pydocstyle (DAR), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge |
| `pytest.ini` | Pytest configuration shared by all generated projects |
| `Makefile` | Targets: `init`, `venv`, `update_venv`, `precommit`, `version_bump_minor`, testing (`test_cov` uses `genbadge`), linting (`lint`, `check_docstrings`), database (`db_up`, `db_backup`, `db_restore`), `run`, `export_context`, `ship`, docs. Offline-only targets (`new_branch`, `git_merge_to_main`, `git_diff_*`) come from `-include make/offline.mk` |
| `tasks.sh` | Non-make equivalent of the project Makefile targets (must stay in sync) |
| `.gitlint` | gitlint length limits (title ≤ 72, body line ≤ 80) — made explicit so they are not discovered only on a late hook rejection |
| `.vscode/settings.json` | Shipped VS Code settings: POSIX interpreter default (Windows path commented), `src` analysis path, pytest, tab-4 Python, INI `files.associations` for `.gitlint`/`.codespellrc`/`.pydocstyle`, poetry env manager |
| `export_context` (target) | Runs `bin/export_repo_content.sh` — script is sourced from `templates/common/bin/` (language-agnostic), copied into the project `bin/` by each scaffold |
| `requirements.txt` | Pins the Poetry version only — not application dependencies |
| `.python-version` | pyenv Python version pin |
| `.gitignore` | Python + Poetry + common IDE patterns |
| `.codespellrc` | codespell configuration |
| `.pydocstyle` | pydocstyle config (NumPy convention, DAR checks) |
| `.coveragerc` | Coverage.py configuration (omits chassis, example_feature, app, config) |
| `poetry.toml` | Poetry local config — forces `virtualenvs.in-project = true` |
| `README.md` | Template README with `${VARIABLE}` placeholders for `envsubst` |
| `.github/workflows/tests.yaml` | CI workflow — copied into the project **only** when a GitHub remote is set up (see `copy_github_assets` in the scaffolds) |
| _(CODEOWNERS, PR template)_ | Language-agnostic; live in `templates/common/.github/`; also GitHub-remote-only |
| `docker-compose.{postgresql,mariadb,mysql}.yml` | DB infra templates; one is copied to `docker-compose.yml` on the docker-compose prompt |
| `src/config/startup.py` | Global runtime config — logger + `output_path()` helper + `PATH_LOG/JSON/TXT`. Always copied into every service project. |
| `src/config/inputs.yaml` | Global inputs — single output root (`daily_infos_base_path`, default `logs`) + `daily_infos_dated` toggle |
| `src/config/outputs.yaml` | Global filename templates (`log/json/txt/csv/xlsx_name`) using **named** placeholders |
| `src/utils/br_identifiers.py` | CNPJ/CPF `mask_*` / `unmask_*` / `is_valid_*` — alphanumeric-aware (2026 CNPJ), pure functions. Copied into every service project's `src/utils/` |
| `src/utils/dtypes.py` | `apply_dtypes(df, dict_dtypes, list_date_cols, list_datetime_cols)` — enforces explicit column typing on load. Copied into every service project's `src/utils/` |
| `src/utils/decimals.py` | `to_decimal(value, int_places, default, rounding)` — precise `Decimal` coercion (BR-number aware), **ROUND_DOWN default**, per-call override |
| `src/utils/loggers.py` | `log_message(logger, str_message, str_level)` — single shared stpstone `CreateLog` entry point |
| `src/utils/text.py` | `normalize_text` — NFKD + accent-strip + casefold; used for allow-list matching (e.g. the webhook production-env gate) |
| `src/utils/paths.py` | `is_windows_path` / `resolve_path` / `ensure_dir` — OS-independent path resolution (Windows paths parsed on POSIX) |
| `src/utils/signatures.py` | `resolve_signature` / `to_html` — e-mail signature HTML resolution |
| `src/utils/dates.py` | ANBIMA business-day helpers (`is_working_day`, `add_working_days`, `delta_working_days`, …) wrapping stpstone `DatesBRAnbima` |
| `optional/typing/` | Runtime type-checking engine (`TypeChecker`, `ABCTypeCheckerMeta`, `ProtocolTypeCheckerMeta`, `@type_checker`, `validate_type`). **Always injected** — to `src/chassis/typing/` (DDD) or `src/utils/typing/` (MVC, via `chassis.typing → utils.typing` rewrite). Preserves static/class/property descriptors; handles PEP 604 `X \| Y` unions |
| `optional/chassis/db/` | `DatabaseHandler` ABC bundle — injected with the schema-less storage opt-in (and always for the native DDD skeleton, whose `db_schema` requires it) |
| `optional/chassis/db_wschema/` | Schema-less storage (JSON/CSV/joblib) — injected on the storage opt-in (DDD only) |
| `optional/storage.env.fragment` | `.env` block appended on the storage opt-in |
| `optional/webhook/` | Port-based webhook provider (`WebhookNotifier` port + teams/slack adapters + `NullNotifier` + `build_webhook(url)`/`detect_platform(url)` factory) — injected on the webhook opt-in; lands in `chassis/webhook` (DDD) or `utils/webhook` (MVC). Platform is inferred from the URL; a blank URL yields a no-op `NullNotifier` |
| `optional/webhooks.yaml` | Webhook message config (named placeholders) — copied on the webhook opt-in |
| `bin/CLAUDE.md` | Shell-script conventions for every `*.sh` in `bin/` |
| `bin/lib/common.sh` | Canonical sourced lib: `print_status`, `_read_env_var`, `resolve_default_branch` (main/master detection), color vars. **Kept byte-identical with `templates/common/bin/lib/common.sh`** — offline scaffolds copy the common-tier version over this one, so both must carry the same functions (do not let them drift) |
| `bin/lib/bootstrap.sh` | Sourced lib: cross-platform resolvers (`bootstrap_init`, `detect_os`, `resolve_python`, `ensure_poetry`), pyenv-preferred/system-Python `ensure_python_version`, `to_native_path` (cygpath path resolution), and `wire_corporate_ca`. Shared by `venv.sh`/`run.sh`/`get_corporate_ca.sh` |
| `bin/lib/pip_fallback.sh` | Sourced lib: Poetry→pip fallback for restricted hosts — parses `pyproject.toml` (Poetry + PEP 621) into pip requirements and installs groups straight into `.venv`. Sourced by `venv.sh`/`run.sh` |
| `bin/venv.sh` | Poetry venv setup — pyenv-preferred with system-Python fallback; configures in-project Poetry venv, upgrades pip in-env, installs `dev,docs`; **falls back to stdlib venv + `pip_fallback`** when Poetry is unavailable. Playwright-aware. Pyenv honoured on both branches |
| _`bin/new_branch.sh`_ | **Offline-only** — lives in `templates/common/bin/`, copied by `apply_offline_mode`, not from here. Create a feature branch off the default branch with CONTRIBUTING-prefix validation; `make new_branch NAME=<x>` |
| _`bin/git_merge_to_main.sh`_ | **Offline-only** — lives in `templates/common/bin/`, copied by `apply_offline_mode`. Merge the current clean branch into the default branch and delete it (uses `--no-verify` to bypass `protect-branch`); `make git_merge_to_main` |
| `bin/get_corporate_ca.sh` | Manual generator for `bin/corporate_ca.pem` — extracts a TLS-inspecting proxy's CA for pypi.org. The pem is git-ignored; its presence opts a project into corporate-SSL mode on the next `make venv` |
| `bin/db.sh` | Database lifecycle with sub-commands `up\|backup\|restore`: `up` starts services, ensures schema, applies migrations; `backup`/`restore` handle pg_dump/pg_restore. Recipes: `db_up`, `db_backup`, `db_restore` |
| `bin/check_docstrings.py` | Pre-commit + `make check_docstrings`: verifies NumPy docstrings against signatures (param/return types, `Raises`). Parses the combined `a, b : type` form; `Raises` is direct-only |
| `bin/ship.sh` | `make ship` — packages the committed default-branch tree into `dist/<repo-kebab>_YYYYMMDD_HHMMSS.zip` (sourced from `templates/common/bin/`) |
| `bin/run.sh` | Run the project entrypoint (auto-resolves `src/main.py` → `src/controller/main.py` → `src/<pkg>/main.py`); skips reinstall when `.venv` is newer than `pyproject.toml`/`poetry.lock`; Poetry→pip→system fallback chain; sources `lib/bootstrap.sh` + `lib/pip_fallback.sh` and wires the corporate CA |
| `bin/check_unix_filenames.sh` | Pre-commit hook: reject filenames with special characters |
| `bin/fix_playwright.sh` | Reinstall Playwright browsers |
| `bin/test_urls_docstrings.sh` | Pre-commit hook: validate URLs in docstrings (1-week cache) |
| `assets/logo_lorem_ipsum.png` | Placeholder logo copied into new projects |
| `CONTRIBUTING.md` | Contribution guide template |

## Editing rules

- **`ruff.toml`**: The active rule sets are `UP E F ANN B SIM I AIR ERA S PD D`. Only `D206` is ignored (tab-indent + docstring conflict). Excluded paths include `alembic`, `src/chassis`, and `src/capabilities/example_feature`. Do not remove rule sets without a documented reason.
- **`.pre-commit-config.yaml`**: Hook versions must stay pinned (`rev:`).
- **`README.md`**: Uses `${VARIABLE}` placeholders — do not replace them with literal values; they are resolved by `envsubst` during scaffolding.
- **`Makefile` ↔ `tasks.sh`**: Must stay in sync. Every target in the Makefile must have a matching function + case branch + help entry in `tasks.sh`. See `bin/CLAUDE.md` for shell conventions.
- **`src/config/*`**: Edit here, never in the skeleton dirs. `startup.py` is generic (plain `datetime.now()`, no domain calendar); the output directory is **data-driven** from `inputs.yaml` (`daily_infos_base_path` + `daily_infos_dated`) — do not hard-code paths or re-add a `folder` key. Filename templates use **named** placeholders, not positional `{}` + comments.
- **`optional/webhook/`**: `SlackNotifier.send` is an intentional contribution stub (raises `NotImplementedError`). The `WebhookNotifier` port is the contract `startup.py` depends on — keep adapters structurally conformant so swapping platforms never touches `startup.py`. Internal imports use the canonical `chassis.webhook` prefix; the MVC scaffolds rewrite it to `utils.webhook` on copy.
- All shell scripts must source `bin/lib/common.sh` and use `print_status` for status output — never bare `echo`/`printf` for status messages.
- **`bin/lib/bootstrap.sh`**: a sourced lib — define-only, no work on source. Callers run `bootstrap_init` before the other helpers. `ensure_python_version` must keep the pyenv-preferred / system-Python fallback (some corporate hosts forbid installing pyenv). `wire_corporate_ca` must stay a no-op when `bin/corporate_ca.pem` is absent, so non-corporate setups keep full TLS verification.
- **`bin/get_corporate_ca.sh`**: the only place TLS verification is intentionally disabled (to capture a proxy CA). Keep it manual (`make get_corporate_ca`) — never auto-run it from `venv.sh`. The generated `bin/corporate_ca.pem` is git-ignored and must never be committed.

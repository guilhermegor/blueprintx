# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`templates/python-common/` is the **single source of truth for shared tooling** across all BlueprintX Python skeletons. Every file here is copied verbatim (or rendered via `envsubst`) into scaffolded projects by each `bin/scaffold/python_*.sh` script.

**Changes here propagate to all Python skeletons on the next scaffold run.**

Most of this directory is *tooling* (ruff, pytest, Makefile, bin scripts). Two subtrees are the **deliberate exceptions** — they hold *application code* that is identical across skeletons, so it lives here rather than being duplicated:

- **`src/config/`** — the global runtime config (`startup.py`, `inputs.yaml`, `outputs.yaml`). **Always** copied into every service project's `src/config/`. This is why the four service skeletons no longer carry their own `startup.py`/`inputs.yaml`/`outputs.yaml`.
- **`optional/`** — opt-in app code injected only when the matching scaffold prompt is answered *yes*. Shipped into the generated project's normal layout (e.g. `src/chassis/`), so the output looks standard — the `optional/` marker exists only here, to keep the tooling-vs-app-code boundary visible.

## Files and their roles

| File / Path | Role |
|-------------|------|
| `ruff.toml` | Ruff lint + format config (line-length 99, tab indent, double quotes, NumPy docstrings, full rule set) |
| `.pre-commit-config.yaml` | Hooks: ruff, pydocstyle (DAR), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge |
| `pytest.ini` | Pytest configuration shared by all generated projects |
| `Makefile` | Targets: `init`, `venv`, `update_venv`, `precommit`, `version_bump_minor`, testing, linting, database, `run`, docs |
| `tasks.sh` | Non-make equivalent of the project Makefile targets (must stay in sync) |
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
| `optional/chassis/db/` | `DatabaseHandler` ABC bundle — injected with the schema-less storage opt-in (and always for the native DDD skeleton, whose `db_schema` requires it) |
| `optional/chassis/db_wschema/` | Schema-less storage (JSON/CSV/joblib) — injected on the storage opt-in (DDD only) |
| `optional/storage.env.fragment` | `.env` block appended on the storage opt-in |
| `optional/webhook/` | Port-based webhook provider (`WebhookNotifier` port + teams/slack adapters + `build_webhook` factory) — injected on the webhook opt-in; lands in `chassis/webhook` (DDD) or `utils/webhook` (MVC) |
| `optional/webhooks.yaml` | Webhook message config (named placeholders) — copied on the webhook opt-in |
| `bin/CLAUDE.md` | Shell-script conventions for every `*.sh` in `bin/` |
| `bin/lib/common.sh` | Canonical sourced lib: `print_status`, `_read_env_var`, color vars |
| `bin/lib/bootstrap.sh` | Sourced lib: cross-platform resolvers (`bootstrap_init`, `detect_os`, `resolve_python`, `ensure_poetry`), pyenv-preferred/system-Python `ensure_python_version`, and `wire_corporate_ca`. Shared by `venv.sh`/`run.sh`/`corporate_ca.sh` |
| `bin/venv.sh` | Poetry venv setup — pyenv-preferred with a system-Python fallback (for hosts without pyenv) + optional corporate-CA wiring; delegates the heavy lifting to `lib/bootstrap.sh` |
| `bin/corporate_ca.sh` | Manual generator for `bin/corporate_ca.pem` — extracts a TLS-inspecting proxy's CA for pypi.org. The pem is git-ignored; its presence opts a project into corporate-SSL mode on the next `make venv` |
| `bin/db_setup_schema.sh` | Idempotent DB setup: start services, ensure schema, apply migrations; also handles backup/restore |
| `bin/run.sh` | Run `src/main.py` via Poetry (auto-installs if absent); sources `lib/bootstrap.sh` to resolve the interpreter and wire the corporate CA |
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
- **`bin/corporate_ca.sh`**: the only place TLS verification is intentionally disabled (to capture a proxy CA). Keep it manual (`make corporate_ca`) — never auto-run it from `venv.sh`. The generated `bin/corporate_ca.pem` is git-ignored and must never be committed.

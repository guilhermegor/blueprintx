# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`templates/python-common/` is the **single source of truth for shared tooling** across all BlueprintX Python skeletons. Every file here is copied verbatim (or rendered via `envsubst`) into scaffolded projects by each `scripts/scaffold/python_*.sh` script.

**Changes here propagate to all three skeletons on the next `make init` run.**

## Files and their roles

| File / Path | Role |
|-------------|------|
| `ruff.toml` | Ruff lint + format config (line-length 99, tab indent, double quotes, NumPy docstrings, full rule set) |
| `.pre-commit-config.yaml` | Hooks: ruff, pydocstyle (DAR), codespell, commitizen, gitlint, hadolint, unit + integration tests, coverage badge |
| `pytest.ini` | Pytest configuration shared by all generated projects |
| `Makefile` | Targets: `init`, `venv`, `update-venv`, `precommit`, testing, linting, `start` |
| `requirements.txt` | Pins the Poetry version only — not application dependencies |
| `.python-version` | pyenv Python version pin |
| `.gitignore` | Python + Poetry + common IDE patterns |
| `.codespellrc` | codespell configuration |
| `.pydocstyle` | pydocstyle config (NumPy convention, DAR checks) |
| `README.md` | Template README with `${VARIABLE}` placeholders for `envsubst` |
| `run.sh` | Non-make equivalent of the project Makefile targets |
| `.github/workflows/tests.yaml` | CI workflow for unit + integration tests |
| `.github/CODEOWNERS` | CODEOWNERS template |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template |
| `bin/` | `check_unix_filenames.sh`, `fix_playwright.sh`, `start.sh`, `test_urls_docstrings.sh` |
| `prompts/` | AI prompt templates: `unit_test.md`, `refactoring.md`, `readme.md` |
| `assets/logo_lorem_ipsum.png` | Placeholder logo copied into new projects |
| `CONTRIBUTING.md` | Contribution guide template |
| `LICENSE` | MIT licence template |

## Editing rules

- **`ruff.toml`**: The active rule sets are `UP E F ANN B SIM I AIR ERA S PD D`. Only `D206` is ignored (tab-indent + docstring conflict). Do not remove rule sets without a documented reason.
- **`.pre-commit-config.yaml`**: Hook versions must stay pinned (`rev:`).
- **`README.md`**: Uses `${VARIABLE}` placeholders — do not replace them with literal values; they are resolved by `envsubst` during scaffolding.
- All shell scripts must remain POSIX-compatible (bash ≥ 4).

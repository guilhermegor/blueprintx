# -------------------
# VIRTUAL ENVIRONMENT
# -------------------
.PHONY: init venv update_venv precommit

init: venv precommit

venv:
	@bash bin/venv.sh

update_venv:
	@poetry update
	@echo "Poetry project updated"

precommit:
	@poetry run pre-commit install
	@poetry run pre-commit install --hook-type commit-msg

version_bump_minor:
	@poetry version minor
	@git add pyproject.toml
	@echo "Version bumped to $$(poetry version -s)"

# -------------------
# CORPORATE CA
# -------------------
.PHONY: get_corporate_ca

get_corporate_ca:
	@bash bin/get_corporate_ca.sh

# -------------------
# TESTING
# -------------------
.PHONY: unit_tests integration_tests test_cov test_slowest test_feat test_urls_docstrings fix_playwright

unit_tests:
	@poetry run pytest tests/unit/

integration_tests:
	@poetry run pytest tests/integration/

test_cov:
	@poetry run pytest tests/unit/ --cov=src
	@poetry run coverage report -m
	@poetry run coverage xml -o coverage.xml
	@poetry run genbadge coverage -i coverage.xml -o coverage.svg

test_slowest:
	@echo "Running tests to identify the 20 slowest tests..."
	@poetry run pytest tests/unit/ --durations=20 --tb=short

test_feat:
	@poetry run pytest tests/unit/ -k "$(FEAT)"

test_urls_docstrings:
	@bash bin/test_urls_docstrings.sh

fix_playwright:
	@bash bin/fix_playwright.sh

# -------------------
# LINTING
# -------------------
.PHONY: lint check_docstrings

lint:
	@poetry run ruff check --fix .
	@poetry run ruff format .
	@poetry run codespell .
	@poetry run pydocstyle .
	@poetry run python bin/check_docstrings.py

check_docstrings:
	@poetry run python bin/check_docstrings.py

# -------------------
# DATABASE
# -------------------
.PHONY: db_up db_backup db_restore

db_up:
	@bash bin/db.sh up

db_backup:
	@bash bin/db.sh backup

db_restore:
	@bash bin/db.sh restore

# -------------------
# RUN
# -------------------
.PHONY: run

run:
	@bash bin/run.sh

# -------------------
# CONTEXT
# -------------------
.PHONY: export_context

export_context:
	@bash bin/export_repo_content.sh

# -------------------
# SHIP
# -------------------
.PHONY: ship

ship:
	@bash bin/ship.sh

# -------------------
# DOCS
# -------------------
.PHONY: docs_server

docs_server:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

# -------------------
# HELP
# -------------------
.PHONY: help

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Virtual Environment"
	@echo "  init                 Bootstrap venv + install pre-commit hooks"
	@echo "  venv                 Create Poetry venv and install dependencies"
	@echo "  update_venv          Update all Poetry dependencies"
	@echo "  precommit            Install pre-commit hooks (push + commit-msg)"
	@echo "  version_bump_minor   Bump minor version in pyproject.toml"
	@echo ""
	@echo "Corporate CA"
	@echo "  get_corporate_ca     Extract a TLS-proxy CA into bin/corporate_ca.pem (corporate networks)"
	@echo ""
	@echo "Testing"
	@echo "  unit_tests           Run unit tests with pytest"
	@echo "  integration_tests    Run integration tests with pytest"
	@echo "  test_cov             Run unit tests with coverage report and badge"
	@echo "  test_slowest         Report the 20 slowest unit tests"
	@echo "  test_feat FEAT=<kw>  Run unit tests matching keyword <kw>"
	@echo "  test_urls_docstrings Check all URLs inside docstrings"
	@echo "  fix_playwright       Reinstall Playwright browsers"
	@echo ""
	@echo "Linting"
	@echo "  lint                 Run ruff, codespell, pydocstyle, check_docstrings"
	@echo "  check_docstrings     Check docstring type/raises consistency"
	@echo ""
	@echo "Database"
	@echo "  db_up                Start Docker services, ensure schema, apply migrations"
	@echo "  db_backup            Dump the database to BACKUP_STORE_PATH"
	@echo "  db_restore DUMP=<p>  Restore database from a dump file at path <p>"
	@echo ""
	@echo "Docs"
	@echo "  docs_server          Serve MkDocs site locally at http://0.0.0.0:8000"
	@echo ""
	@echo "Run"
	@echo "  run                  Run src/main.py (auto-installs Poetry if missing)"
	@echo ""
	@echo "Context / Ship"
	@echo "  export_context       Flatten the repo into repo_context.txt for pasting into a web-UI LLM"
	@echo "  ship                 Package the committed main tree into dist/<name>_<ts>.zip"
	@echo ""
	@echo "Offline (only present when scaffolded without GitHub)"
	@echo "  new_branch NAME=<x>  Create a branch (feat/…, fix/…) off the default branch (main/master)"
	@echo "  git_merge_to_main    Merge the current clean branch into main/master and delete it"
	@echo "  git_diff_export              Export commits (DIFF_RANGE, default main..HEAD) to git_diffs/"
	@echo "  git_diff_check FILE=<path>   Check whether a .diff applies cleanly"
	@echo "  git_diff_apply FILE=<path>   Apply a .diff to the working tree (no commit)"
	@echo ""

# Offline-only targets (new_branch, git_merge_to_main, git_diff_*) — present only
# when scaffolded without GitHub. The leading '-' silently skips this when absent.
-include make/offline.mk

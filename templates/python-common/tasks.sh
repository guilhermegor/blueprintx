#!/usr/bin/env bash
# tasks.sh — Bash alternative to Makefile (no make required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------
# VIRTUAL ENVIRONMENT
# -------------------

venv() {
	bash "$SCRIPT_DIR/bin/venv.sh"
}

update_venv() {
	poetry update
	echo "Poetry project updated"
}

precommit() {
	poetry run pre-commit install
	poetry run pre-commit install --hook-type commit-msg
}

init() {
	venv
	precommit
}

version_bump_minor() {
	poetry version minor
	git add pyproject.toml
	echo "Version bumped to $(poetry version -s)"
}

# -------------------
# CORPORATE CA
# -------------------

get_corporate_ca() {
	bash "$SCRIPT_DIR/bin/get_corporate_ca.sh"
}

# -------------------
# TESTING
# -------------------

unit_tests() {
	poetry run pytest tests/unit/
}

integration_tests() {
	poetry run pytest tests/integration/
}

test_cov() {
	poetry run pytest tests/unit/ --cov=src
	poetry run coverage report -m
	poetry run coverage xml -o coverage.xml
	poetry run genbadge coverage -i coverage.xml -o coverage.svg
}

test_slowest() {
	echo "Running tests to identify the 20 slowest tests..."
	poetry run pytest tests/unit/ --durations=20 --tb=short
}

test_feat() {
	if [[ -z "${FEAT:-}" ]]; then
		echo "Usage: FEAT=<keyword> ./tasks.sh test_feat"
		exit 1
	fi
	poetry run pytest tests/unit/ -k "$FEAT"
}

test_urls_docstrings() {
	bash "$SCRIPT_DIR/bin/test_urls_docstrings.sh"
}

fix_playwright() {
	bash "$SCRIPT_DIR/bin/fix_playwright.sh"
}

# -------------------
# LINTING
# -------------------

lint() {
	poetry run ruff check --fix .
	poetry run ruff format .
	poetry run codespell .
	poetry run pydocstyle .
	poetry run python bin/check_docstrings.py
}

check_docstrings() {
	poetry run python bin/check_docstrings.py
}

# -------------------
# DATABASE
# -------------------

db_up() {
	bash "$SCRIPT_DIR/bin/db.sh" up
}

db_backup() {
	bash "$SCRIPT_DIR/bin/db.sh" backup
}

db_restore() {
	bash "$SCRIPT_DIR/bin/db.sh" restore
}

# -------------------
# RUN
# -------------------

run() {
	bash "$SCRIPT_DIR/bin/run.sh"
}

# -------------------
# SHIP
# -------------------

ship() {
	bash "$SCRIPT_DIR/bin/ship.sh"
}

# -------------------
# OFFLINE (defined only when scaffolded without GitHub)
# -------------------
# new_branch, git_merge_to_main and the git_diff_* helpers substitute for the
# GitHub branch/PR flow; they ship only in offline mode (their scripts live in
# bin/ only then). Define each function only when its script is present.

if [ -f "$SCRIPT_DIR/bin/new_branch.sh" ]; then
	new_branch() { bash "$SCRIPT_DIR/bin/new_branch.sh" "${1:-}"; }
fi

if [ -f "$SCRIPT_DIR/bin/git_merge_to_main.sh" ]; then
	git_merge_to_main() { bash "$SCRIPT_DIR/bin/git_merge_to_main.sh" "${1:-}"; }
fi

if [ -f "$SCRIPT_DIR/bin/git_diff_export.sh" ]; then
	git_diff_export() { bash "$SCRIPT_DIR/bin/git_diff_export.sh"; }
	git_diff_check() { bash "$SCRIPT_DIR/bin/git_diff_check.sh" "${1:-}"; }
	git_diff_apply() { bash "$SCRIPT_DIR/bin/git_diff_apply.sh" "${1:-}"; }
fi

# -------------------
# DOCS
# -------------------

docs_server() {
	poetry install --with docs
	poetry run mkdocs serve -a 0.0.0.0:8000 --livereload
}

# -------------------
# CONTEXT
# -------------------

export_context() {
	bash "$SCRIPT_DIR/bin/export_repo_content.sh" "${1:-}"
}

# -------------------
# HELP
# -------------------

show_help() {
	cat <<EOF

Usage: ./tasks.sh <command>

Virtual Environment
  init                 Bootstrap venv + install pre-commit hooks
  venv                 Create Poetry venv and install dependencies
  update_venv          Update all Poetry dependencies
  precommit            Install pre-commit hooks (push + commit-msg)
  version_bump_minor   Bump minor version in pyproject.toml

Corporate CA
  get_corporate_ca     Extract a TLS-proxy CA into bin/corporate_ca.pem (corporate networks)

Testing
  unit_tests           Run unit tests with pytest
  integration_tests    Run integration tests with pytest
  test_cov             Run unit tests with coverage report and badge
  test_slowest         Report the 20 slowest unit tests
  FEAT=<kw> test_feat  Run unit tests matching keyword <kw>
  test_urls_docstrings Check all URLs inside docstrings
  fix_playwright       Reinstall Playwright browsers

Linting
  lint                 Run ruff, codespell, pydocstyle, check_docstrings
  check_docstrings     Check docstring type/raises consistency

Database
  db_up                Start Docker services, ensure schema, apply migrations
  db_backup            Dump the database to BACKUP_STORE_PATH
  db_restore           Restore database from DUMP=<path>

Docs
  docs_server          Serve MkDocs site locally at http://0.0.0.0:8000

Run
  run                  Run src/main.py (auto-installs Poetry if missing)

Context / Ship
  export_context       Flatten the repo into repo_context.txt for pasting into a web-UI LLM
  ship                 Package the committed main tree into dist/<name>_<ts>.zip

Offline (only present when scaffolded without GitHub)
  NAME=<x> new_branch  Create a branch (feat/…, fix/…) off the default branch (main/master)
  git_merge_to_main    Merge the current clean branch into main/master and delete it
  git_diff_export             Export commits (DIFF_RANGE, default main..HEAD) to git_diffs/
  git_diff_check <path>       Check whether a .diff applies cleanly
  git_diff_apply <path>       Apply a .diff to the working tree (no commit)

EOF
}

# -------------------
# MAIN
# -------------------

case "${1:-help}" in
	init)                init ;;
	venv)                venv ;;
	update_venv)         update_venv ;;
	precommit)           precommit ;;
	version_bump_minor)  version_bump_minor ;;
	get_corporate_ca)    get_corporate_ca ;;
	unit_tests)          unit_tests ;;
	integration_tests)   integration_tests ;;
	test_cov)            test_cov ;;
	test_slowest)        test_slowest ;;
	test_feat)           test_feat ;;
	test_urls_docstrings) test_urls_docstrings ;;
	fix_playwright)      fix_playwright ;;
	lint)                lint ;;
	check_docstrings)    check_docstrings ;;
	db_up)               db_up ;;
	db_backup)           db_backup ;;
	db_restore)          db_restore ;;
	docs_server)         docs_server ;;
	run)                 run ;;
	export_context)      export_context "${2:-}" ;;
	ship)                ship ;;
	new_branch)          new_branch "${2:-}" ;;
	git_merge_to_main)   git_merge_to_main "${2:-}" ;;
	git_diff_export)     git_diff_export ;;
	git_diff_check)      git_diff_check "${2:-}" ;;
	git_diff_apply)      git_diff_apply "${2:-}" ;;
	help|--help|-h)      show_help ;;
	*)
		echo "Unknown command: $1"
		show_help
		exit 1
		;;
esac

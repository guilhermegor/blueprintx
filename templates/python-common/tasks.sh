#!/usr/bin/env bash
# tasks.sh — Bash alternative to Makefile (no make required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Every Poetry call routes through bin/poetry_exec.sh, which resolves Poetry
# (poetry -> python -m poetry) on THIS machine — so no task depends on a bare
# `poetry` being on PATH. Resolution chatter goes to stderr, so $(poetry_exec …)
# command substitution stays clean. Kept in lockstep with the Makefile's POETRY var.
poetry_exec() {
	bash "$SCRIPT_DIR/bin/poetry_exec.sh" "$@"
}

# -------------------
# VIRTUAL ENVIRONMENT
# -------------------

ensure_env() {
	bash "$SCRIPT_DIR/bin/ensure_env.sh"
}

venv() {
	bash "$SCRIPT_DIR/bin/venv.sh"
}

update_venv() {
	poetry_exec update
	echo "Poetry project updated"
}

precommit() {
	# Hook install lives in bin/precommit.sh so it skips gracefully on a non-git
	# deploy tree instead of aborting init.
	bash "$SCRIPT_DIR/bin/precommit.sh"
}

init() {
	# Seed .env first; a failed seed is non-blocking so init still runs venv +
	# precommit — mirrors the Makefile's '-@' on ensure_env.
	ensure_env || true
	venv
	precommit
}

bump_version() {
	# LEVEL is any Poetry bump rule (patch|minor|major|premajor|preminor|prepatch|
	# prerelease) or an explicit version (e.g. 1.4.0); Poetry validates it and fails
	# loud on a bad value. Accepts LEVEL=<x> (parity with the Makefile) or a positional
	# argument; defaults to patch.
	local str_level="${LEVEL:-${1:-patch}}"
	poetry_exec version "$str_level"
	git add pyproject.toml
	echo "Version bumped to $(poetry_exec version -s)"
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
	poetry_exec run pytest tests/unit/
}

integration_tests() {
	poetry_exec run pytest tests/integration/
}

test_cov() {
	poetry_exec run pytest tests/unit/ --cov=src
	poetry_exec run coverage report -m
	poetry_exec run coverage xml -o coverage.xml
	poetry_exec run genbadge coverage -i coverage.xml -o coverage.svg
}

test_cov_report() {
	poetry_exec run pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html
	echo "HTML coverage report at htmlcov/index.html"
}

test_cov_serve() {
	(cd htmlcov && python3 -m http.server "${PORT:-8000}")
}

test_slowest() {
	echo "Running tests to identify the 20 slowest tests..."
	poetry_exec run pytest tests/unit/ --durations=20 --tb=short
}

test_feat() {
	if [[ -z "${FEAT:-}" ]]; then
		echo "Usage: FEAT=<keyword> ./tasks.sh test_feat"
		exit 1
	fi
	poetry_exec run pytest tests/unit/ -k "$FEAT"
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
	poetry_exec run ruff check --fix .
	poetry_exec run ruff format .
	(cd src && poetry_exec run mypy --config-file ../mypy.ini .)
	poetry_exec run codespell .
	poetry_exec run pydocstyle .
	poetry_exec run python bin/check_docstrings.py
	bash "$SCRIPT_DIR/bin/lint_shell.sh"
	bash "$SCRIPT_DIR/bin/lint_sql.sh"
	bash "$SCRIPT_DIR/bin/lint_yaml.sh"
}

check_docstrings() {
	poetry_exec run python bin/check_docstrings.py
}

install_shell_linters() {
	# Optional system-binary install of shellcheck + shfmt. The primary route is pip
	# (shellcheck-py/shfmt-py dev-deps); this helps boxes whose venv drive blocks the
	# vendored binary.
	bash "$SCRIPT_DIR/bin/install_shell_linters.sh"
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
	poetry_exec install --with docs
	poetry_exec run mkdocs serve -a 0.0.0.0:8000 --livereload
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
  init                 Seed .env, bootstrap venv, install pre-commit hooks
  ensure_env           Seed .env from .env.example if .env is missing
  venv                 Create Poetry venv and install dependencies
  update_venv          Update all Poetry dependencies
  precommit            Install pre-commit hooks (commit-msg + pre-push; skips off a git tree)
  bump_version         Bump version: LEVEL=<patch|minor|major|pre*|X.Y.Z> (default patch); also accepts a positional arg

Corporate CA
  get_corporate_ca     Extract a TLS-proxy CA into bin/corporate_ca.pem (corporate networks)

Testing
  unit_tests           Run unit tests with pytest
  integration_tests    Run integration tests with pytest
  test_cov             Run unit tests with coverage report and badge
  test_cov_report      Coverage with term-missing + HTML report (htmlcov/)
  PORT=<n> test_cov_serve  Serve htmlcov/ at http://localhost:<n> (default 8000)
  test_slowest         Report the 20 slowest unit tests
  FEAT=<kw> test_feat  Run unit tests matching keyword <kw>
  test_urls_docstrings Check all URLs inside docstrings
  fix_playwright       Reinstall Playwright browsers

Linting
  lint                 Run ruff, mypy, codespell, pydocstyle, check_docstrings, shell/sql/yaml
  check_docstrings     Check docstring type/raises consistency
  install_shell_linters  Install shellcheck + shfmt as system binaries (optional; pip is primary)

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
init) init ;;
ensure_env) ensure_env ;;
venv) venv ;;
update_venv) update_venv ;;
precommit) precommit ;;
bump_version) bump_version "${2:-}" ;;
get_corporate_ca) get_corporate_ca ;;
unit_tests) unit_tests ;;
integration_tests) integration_tests ;;
test_cov) test_cov ;;
test_cov_report) test_cov_report ;;
test_cov_serve) test_cov_serve ;;
test_slowest) test_slowest ;;
test_feat) test_feat ;;
test_urls_docstrings) test_urls_docstrings ;;
fix_playwright) fix_playwright ;;
lint) lint ;;
check_docstrings) check_docstrings ;;
install_shell_linters) install_shell_linters ;;
db_up) db_up ;;
db_backup) db_backup ;;
db_restore) db_restore ;;
docs_server) docs_server ;;
run) run ;;
export_context) export_context "${2:-}" ;;
ship) ship ;;
new_branch) new_branch "${2:-}" ;;
git_merge_to_main) git_merge_to_main "${2:-}" ;;
git_diff_export) git_diff_export ;;
git_diff_check) git_diff_check "${2:-}" ;;
git_diff_apply) git_diff_apply "${2:-}" ;;
help | --help | -h) show_help ;;
*)
	echo "Unknown command: $1"
	show_help
	exit 1
	;;
esac

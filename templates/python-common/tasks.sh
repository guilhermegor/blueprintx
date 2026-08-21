#!/usr/bin/env bash
# tasks.sh — Bash alternative to Makefile (no make required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# print_status lives in bin/lib/common.sh. Sourcing it is NOT optional: tasks.sh already calls
# print_status, and without this line those calls die "command not found" (exit 127) — which
# under `set -e` aborts the task. Measured: `./tasks.sh init` exited 127 at enable_repo_rules,
# so enable_repo_rules and enable_security never ran in ANY scaffolded project. The Makefile
# was unaffected (its recipes shell out to bin/*.sh, which source the lib themselves), so the
# break was invisible to anyone using `make` — and tasks.sh is precisely the interface for a
# box without make, i.e. the one least able to diagnose it.
# shellcheck source=bin/lib/common.sh
source "$SCRIPT_DIR/bin/lib/common.sh"

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

enable_pages() {
	# Enable GitHub Pages once, with the source matching this project's docs model (auto-detected
	# from mkdocs.yml): mike (versioned) serves from the gh-pages branch — only once that branch
	# exists — otherwise source = GitHub Actions so the docs deploy workflow can publish.
	# Lives in bin/enable_pages.sh; idempotent + non-blocking (skips without gh/auth,
	# no remote, or non-admin), so init still completes for contributors and offline scaffolds.
	bash "$SCRIPT_DIR/bin/enable_pages.sh"
}

enable_repo_rules() {
	print_status "info" "Applying the pr-quality-gate ruleset + merge settings..."
	# Lives in bin/enable_repo_rules.sh; idempotent + non-blocking (skips without gh/auth,
	# without a remote, or without repo-admin), so it never fails init.
	bash "$SCRIPT_DIR/bin/enable_repo_rules.sh"
}

enable_security() {
	print_status "info" "Enabling the GitHub security toggles..."
	# Lives in bin/enable_security.sh; same admin-gated, idempotent, non-blocking contract.
	bash "$SCRIPT_DIR/bin/enable_security.sh"
}

init() {
	# Seed .env first; a failed seed is non-blocking so init still runs venv +
	# precommit — mirrors the Makefile's '-@' on ensure_env.
	ensure_env || true
	venv
	precommit
	enable_pages
	enable_repo_rules
	enable_security
}

bump_version() {
	# cz computes the next semver from Conventional Commits, writes it to pyproject.toml,
	# regenerates CHANGELOG.md, commits "bump: X.Y.Z", and creates the vX.Y.Z tag.
	# --no-verify bypasses the commit hooks for this machine-generated commit: its single-line
	# "bump: …" message can't satisfy gitlint's body-required rule, and the pre-commit
	# test/format hooks are irrelevant to a pyproject + CHANGELOG bump (same rationale as
	# bin/git_merge_to_main.sh). Run this on a feature branch (before `git_merge_to_main`).
	poetry_exec run cz bump --yes --no-verify --git-output-to-stderr
	echo "Version bumped to $(poetry_exec run cz version --project 2>/dev/null || poetry_exec version -s)"
}

changelog() {
	# Regenerate CHANGELOG.md from git tags + Conventional Commits (cz derives sections
	# from tags). Preview locally; the published site regenerates it in the docs workflow.
	# CI never commits it.
	poetry_exec run cz changelog
	echo "CHANGELOG.md regenerated"
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
	poetry_exec run genbadge coverage --local -i coverage.xml -o coverage.svg # --local: render offline, never fetch shields.io
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
	poetry_exec run python bin/check_layer_imports.py
	poetry_exec run python bin/check_comment_language.py
	bash "$SCRIPT_DIR/bin/lint_shell.sh"
	bash "$SCRIPT_DIR/bin/lint_sql.sh"
	bash "$SCRIPT_DIR/bin/lint_yaml.sh"
	bash "$SCRIPT_DIR/bin/lint_actions.sh"
}

check_docstrings() {
	poetry_exec run python bin/check_docstrings.py
}

check_commit_msg() {
	# Pre-flight a commit message BEFORE `git commit -F <file>`. commitizen and gitlint reject
	# at the commit-msg stage — after every pre-commit gate has already run — so each rejected
	# message costs a full gate run, and the fixes arrive one at a time. Invokes the project's
	# OWN hooks, so it cannot drift from what the commit will enforce.
	# FILE=<path>, matching the Makefile's `make check_commit_msg FILE=<path>` and the
	# FEAT=/DUMP= convention already used in this file.
	if [ -z "${FILE:-}" ]; then
		print_status "error" "Usage: FILE=<message-file> ./tasks.sh check_commit_msg"
		return 2
	fi
	poetry_exec run pre-commit run --hook-stage commit-msg --commit-msg-filename "$FILE"
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
# LIBRARY (defined only when scaffolded as a distributable library)
# -------------------
# install_dist_locally ships only for the library tier (make/library.mk present); it mirrors
# the Makefile's -included library target. Defined only when the marker is there.

if [ -f "$SCRIPT_DIR/make/library.mk" ]; then
	install_dist_locally() {
		# `python -m build` (a PEP 517 frontend) so poetry-dynamic-versioning stamps the real
		# version into the wheel; `poetry build` would ignore the backend. The editable install
		# resolves __version__ to the 0.0.0 placeholder (expected), so report the built wheel's
		# actual tag-derived version. The package name is read from pyproject at runtime.
		rm -rf dist/* build/ ./*.egg-info/
		poetry_exec run python -m build
		poetry_exec install
		local str_pkg
		str_pkg=$(poetry_exec version | awk '{print $1}' | tr '-' '_')
		poetry_exec run python -c "import importlib, sys; m = importlib.import_module(sys.argv[1]); assert m.__version__; print('Package import works; __version__ resolves')" "$str_pkg"
		poetry_exec run python -c "import pathlib; print('Built wheel:', sorted(pathlib.Path('dist').glob('*.whl'))[-1].name)"
	}
fi

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

export_deps() {
	bash "$SCRIPT_DIR/bin/export_deps.sh"
}

# -------------------
# HELP
# -------------------

show_help() {
	# The command list lives in bin/help.txt, read by BOTH this and `make help`.
	# It was duplicated — a heredoc here and ~65 `@echo` lines in the Makefile — with a
	# CLAUDE.md rule telling humans to keep them in sync. They had already drifted:
	# `make help` was missing test_cov_report and test_cov_serve entirely, so two real
	# targets were undiscoverable from the entry point most people use. One file makes
	# the drift impossible instead of forbidden.
	printf '\nUsage: ./tasks.sh <command>\n\n'
	cat "$(dirname "${BASH_SOURCE[0]}")/bin/help.txt"
	printf '\n'
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
enable_pages) enable_pages ;;
enable_repo_rules) enable_repo_rules ;;
enable_security) enable_security ;;
bump_version) bump_version ;;
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
check_commit_msg) check_commit_msg ;;
install_shell_linters) install_shell_linters ;;
db_up) db_up ;;
db_backup) db_backup ;;
db_restore) db_restore ;;
docs_server) docs_server ;;
run) run ;;
export_context) export_context "${2:-}" ;;
export_deps) export_deps ;;
ship) ship ;;
install_dist_locally) install_dist_locally ;;
changelog) changelog ;;
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

# Every Poetry call routes through bin/poetry_exec.sh, which resolves Poetry
# (poetry -> python -m poetry) on THIS machine — so no recipe depends on a bare
# `poetry` being on PATH (which breaks after a `pip install --user` Poetry on
# Windows/Git Bash). Never call a bare `poetry` in a recipe.
POETRY := bash bin/poetry_exec.sh

# -------------------
# VIRTUAL ENVIRONMENT
# -------------------
.PHONY: init ensure_env venv update_venv precommit enable_pages enable_repo_rules enable_security bump_version changelog

init: ensure_env venv precommit enable_pages enable_repo_rules enable_security

# Seed .env from .env.example for a fresh checkout. The leading '-' makes a failed
# seed (e.g. no .env.example) non-blocking for init — venv + precommit still run.
ensure_env:
	-@bash bin/ensure_env.sh

venv:
	@bash bin/venv.sh

update_venv:
	@$(POETRY) update
	@echo "Poetry project updated"

# Pre-commit hook install lives in bin/precommit.sh so it can skip gracefully on a
# non-git deploy tree (a shipped zip with no .git) instead of aborting init.
precommit:
	@bash bin/precommit.sh

# Enable GitHub Pages once, with the source matching this project's docs model — auto-detected
# from mkdocs.yml: mike (versioned) serves from the gh-pages BRANCH, otherwise source = GitHub
# Actions. The mike path waits until the gh-pages branch exists (the first release deploy creates
# it), so Pages is never pointed at an empty branch.
# The workflow's GITHUB_TOKEN is a GitHub App token that CAN'T create the Pages site itself
# (first run fails "Resource not accessible by integration"); this uses the maintainer's gh
# auth. bin/enable_pages.sh is idempotent + non-blocking — it skips (never fails init) when gh
# is absent/unauthenticated, no remote resolves, or the caller isn't a repo admin, so
# contributors and offline scaffolds run it harmlessly.
enable_pages:
	@bash bin/enable_pages.sh

# Provision the `pr-quality-gate` branch ruleset + the repo settings the PR gate needs
# (CodeQL default setup, allow_auto_merge, delete_branch_on_merge, the do-not-merge label).
# Repo-settings writes need the maintainer's gh auth — CI's GITHUB_TOKEN cannot make them.
# Idempotent + non-blocking, so it never fails init.
enable_repo_rules:
	@bash bin/enable_repo_rules.sh

# Flip the free GitHub security toggles: private vulnerability reporting, Dependabot alerts,
# and Dependabot security updates. Same admin-gated, idempotent, non-blocking contract.
enable_security:
	@bash bin/enable_security.sh

# Cut a version bump from Conventional Commits: cz computes the next semver, writes it to
# pyproject.toml, regenerates CHANGELOG.md, commits "bump: X.Y.Z", and creates the vX.Y.Z tag.
# --git-output-to-stderr keeps stdout clean. --no-verify bypasses the commit hooks for this
# machine-generated commit: its single-line "bump: …" message can't satisfy gitlint's
# body-required rule, and the pre-commit test/format hooks are irrelevant to a pyproject +
# CHANGELOG bump (same rationale as bin/git_merge_to_main.sh's --no-verify). Run this on a
# feature branch (before `make git_merge_to_main`). OFFLINE tier only — the online scaffold
# strips this target (releases are cut by the release.yaml workflow).
bump_version:
	@$(POETRY) run cz bump --yes --no-verify --git-output-to-stderr
	@echo "Version bumped to $$($(POETRY) run cz version --project 2>/dev/null || $(POETRY) version -s)"

# Regenerate CHANGELOG.md from git tags + Conventional Commits (cz derives sections from tags).
# Preview locally; the published site regenerates it in the docs workflow. CI never commits it.
changelog:
	@$(POETRY) run cz changelog
	@echo "CHANGELOG.md regenerated"

# -------------------
# CORPORATE CA
# -------------------
.PHONY: get_corporate_ca

get_corporate_ca:
	@bash bin/get_corporate_ca.sh

# -------------------
# TESTING
# -------------------
.PHONY: unit_tests integration_tests test_cov test_cov_report test_cov_serve test_slowest test_feat test_urls_docstrings fix_playwright

unit_tests:
	@$(POETRY) run pytest tests/unit/

integration_tests:
	@$(POETRY) run pytest tests/integration/

test_cov:
	@$(POETRY) run pytest tests/unit/ --cov=src
	@$(POETRY) run coverage report -m
	@$(POETRY) run coverage xml -o coverage.xml
	@$(POETRY) run genbadge coverage --local -i coverage.xml -o coverage.svg  # --local: render offline, never fetch shields.io

# Whole-tree HTML coverage for drill-down (never narrow --cov=<module>, which
# reports "no data" on the full suite). Open htmlcov/index.html or `make test_cov_serve`.
test_cov_report:
	@$(POETRY) run pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html
	@echo "HTML coverage report at htmlcov/index.html"

test_cov_serve:
	@cd htmlcov && python3 -m http.server $${PORT:-8000}

test_slowest:
	@echo "Running tests to identify the 20 slowest tests..."
	@$(POETRY) run pytest tests/unit/ --durations=20 --tb=short

test_feat:
	@$(POETRY) run pytest tests/unit/ -k "$(FEAT)"

test_urls_docstrings:
	@bash bin/test_urls_docstrings.sh

fix_playwright:
	@bash bin/fix_playwright.sh

# -------------------
# LINTING
# -------------------
.PHONY: lint check_docstrings check_function_length check_commit_msg install_shell_linters

# Optional: install shellcheck + shfmt as SYSTEM binaries (choco/scoop/brew/apt).
# The primary route is pip (shellcheck-py/shfmt-py dev-deps via `poetry install`);
# this is only for boxes whose venv drive blocks executing the vendored binary.
install_shell_linters:
	@bash bin/install_shell_linters.sh

lint:
	@$(POETRY) run ruff check --fix .
	@$(POETRY) run ruff format .
	@cd src && bash ../bin/poetry_exec.sh run mypy --config-file ../mypy.ini .
	@$(POETRY) run codespell .
	@$(POETRY) run pydocstyle .
	@$(POETRY) run python bin/check_docstrings.py
	@$(POETRY) run python bin/check_layer_imports.py
	@$(POETRY) run python bin/check_comment_language.py
	@$(POETRY) run python bin/check_function_length.py
	@bash bin/lint_shell.sh
	@bash bin/lint_sql.sh
	@bash bin/lint_yaml.sh
	@bash bin/lint_actions.sh

check_docstrings:
	@$(POETRY) run python bin/check_docstrings.py

# Also reachable on its own, so the one rule can be checked without paying for the whole
# lint set. `make lint` covers it above.
check_function_length:
	@$(POETRY) run python bin/check_function_length.py

# Pre-flight a commit message BEFORE `git commit -F <file>`.
#
# commitizen and gitlint reject at the commit-msg stage — i.e. AFTER every pre-commit gate has
# already run — so each rejected message costs a full gate run, and the fixes come one at a
# time (title too long, then a body line too long, then the next one). This runs only the
# commit-msg hooks against a message file, in seconds:
#
#   printf 'fix(scope): message\n' > .commitmsg
#   make check_commit_msg FILE=.commitmsg && git commit -F .commitmsg
#
# It invokes the project's OWN hooks, so it cannot drift from what the commit will enforce.
# When re-wrapping an over-long body line, re-wrap the whole paragraph
# (`textwrap.fill(width=76)`) — fixing one line by hand pushes the overflow into the next.
check_commit_msg:
	@test -n "$(FILE)" || { echo "usage: make check_commit_msg FILE=<message-file>" >&2; exit 2; }
	@$(POETRY) run pre-commit run --hook-stage commit-msg --commit-msg-filename "$(FILE)"

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
.PHONY: export_context export_deps

export_context:
	@bash bin/export_repo_content.sh

# Locked deps as requirements-lock.txt, for hosts that can pip but not Poetry.
export_deps:
	@bash bin/export_deps.sh

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
	@$(POETRY) install --with docs
	@$(POETRY) run mkdocs serve -a 0.0.0.0:8000 --livereload

# -------------------
# HELP
# -------------------
.PHONY: help

help:
	@printf '\nUsage: make <target>\n\n'
	@cat bin/help.txt
	@printf '\n'

# Library-only targets (install_dist_locally) — present only when scaffolded as a
# distributable library (lib-minimal). The leading '-' silently skips this when absent.
-include make/library.mk

# Offline-only targets (new_branch, git_merge_to_main, git_diff_*) — present only
# when scaffolded without GitHub. The leading '-' silently skips this when absent.
-include make/offline.mk

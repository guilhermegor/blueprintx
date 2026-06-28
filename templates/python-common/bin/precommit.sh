#!/usr/bin/env bash
# Install the pre-commit hooks (commit-msg + pre-push) for `make init` / `tasks.sh init`.
#
# pre-commit writes hooks into .git/hooks, so `pre-commit install` requires (a) git
# on PATH and (b) a git work tree. On a runtime/deploy box — e.g. a shipped zip
# unpacked outside any git checkout — there is no .git, and pre-commit aborts with
# "FatalError: git failed. Is it installed, and are you in a Git repository
# directory?", taking `init` down with it.
#
# Contract (template default): hooks are a dev-only concern, so when there is no git
# work tree (or git itself is absent) we WARN and SKIP — `init` still completes the
# essential steps (venv). This mirrors the best-effort treatment of `ensure_env` and
# the Playwright browser install.
#
# Opt-in alternative: if you want a deploy box to BECOME a git repo so hooks install,
# replace the skip in ensure_git_repo with a loud `git init` (announce it so a *dev*
# box surfaces a lost .git instead of silently fabricating an empty repo). Never
# auto-init silently.
#
# Poetry is resolved via bin/lib/bootstrap.sh (poetry -> python -m poetry), never a
# bare `poetry` — see bin/poetry_exec.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

ensure_git_repo() {
	# Confirm the current tree is a git work tree with git available. Returns 1
	# (caller skips) when git is absent or there is no work tree — never aborts init.
	if ! command -v git >/dev/null 2>&1; then
		print_status "warning" "git not found — skipping pre-commit hooks (a runtime box never commits)"
		return 1
	fi

	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		print_status "warning" "No git repository here — skipping pre-commit hooks (run inside a checkout to install them)"
		return 1
	fi

	return 0
}

install_hooks() {
	print_status "info" "Installing pre-commit hooks (commit-msg + pre-push)..."
	run_poetry run pre-commit install
	run_poetry run pre-commit install --hook-type commit-msg
	run_poetry run pre-commit install --hook-type pre-push
	print_status "success" "Pre-commit hooks installed"
}

main() {
	print_status "section" "Pre-commit Hook Setup"

	# No git work tree → nothing to install into; skip so init still completes.
	if ! ensure_git_repo; then
		return 0
	fi

	# Resolve Poetry robustly, then install. A failure here is genuine and propagates.
	bootstrap_init
	if ! ensure_poetry; then
		print_status "error" "Poetry could not be resolved — cannot install pre-commit hooks"
		return 1
	fi
	install_hooks
}

main "$@"

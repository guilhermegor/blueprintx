#!/usr/bin/env bash
#
# lint_shell.sh — shellcheck + shfmt over the project's shell scripts.
#
# Single source of truth for shell linting: called by both `make lint` /
# `./tasks.sh lint` and the pre-commit `lint-shell` hook. shellcheck and shfmt are
# SYSTEM binaries (not pip/poetry installable), so each is GUARDED with `command -v`
# and SKIPPED gracefully (exit 0 + a message) when absent — a constrained box (e.g.
# Windows prod with no apt/brew/go) never hard-fails the lint/commit flow.
#
# Modes:
#   (default)  shfmt -w  — format in place (matches `ruff format` in `make lint`).
#   --check    shfmt -d  — diff only, non-mutating (used by the pre-commit gate).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

bool_check=false
if [[ "${1:-}" == "--check" ]]; then
	bool_check=true
fi

# The shell files to lint: the task runner and the bin scripts/libs.
mapfile -t list_files < <(
	cd "$SCRIPT_DIR/.." && {
		printf '%s\n' tasks.sh
		find bin -name '*.sh' -type f
	}
)

if command -v shellcheck >/dev/null 2>&1; then
	print_status info "shellcheck: ${#list_files[@]} script(s)"
	# Canonical gate (see bin/CLAUDE.md): warning-and-above, SC1091 excluded globally
	# (siblings are sourced via runtime paths shellcheck cannot follow). Flags are
	# explicit (not just .shellcheckrc) so the gate is identical wherever it runs.
	(cd "$SCRIPT_DIR/.." && shellcheck --severity=warning --exclude=SC1091 "${list_files[@]}")
	print_status success "shellcheck OK"
else
	print_status warning "skip: shellcheck not installed (apt/brew install shellcheck)"
fi

if command -v shfmt >/dev/null 2>&1; then
	if [[ "$bool_check" == true ]]; then
		print_status info "shfmt --check (diff only)"
		(cd "$SCRIPT_DIR/.." && shfmt -d "${list_files[@]}")
	else
		print_status info "shfmt -w (format in place)"
		(cd "$SCRIPT_DIR/.." && shfmt -w "${list_files[@]}")
	fi
	print_status success "shfmt OK"
else
	print_status warning "skip: shfmt not installed (go install mvdan.cc/sh/v3/cmd/shfmt@latest)"
fi

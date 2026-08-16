#!/usr/bin/env bash
#
# lint_actions.sh — actionlint over the repository's GitHub Actions workflows.
#
# WHY THIS EXISTS: yamllint validates YAML; actionlint validates a WORKFLOW. They answer
# different questions, and only the second one is the question GitHub asks.
#
#   | tool       | question                                  | verdict on the defect below |
#   |------------|-------------------------------------------|-----------------------------|
#   | yamllint   | is this well-formed, consistent YAML?     | PASSED                      |
#   | actionlint | is this a workflow GitHub will run?       | unknown Webhook event       |
#
# Measured: a workflow added `pull_request_review_thread` to `on:` — a real webhook event,
# but NOT a workflow trigger. Impeccable YAML, so yamllint and every local hook passed.
# GitHub then rejected the ENTIRE FILE ("This run likely failed because of a workflow file
# issue").
#
# ⚠️ THE FAILURE IS TOTAL AND DISGUISES ITSELF AS SLOWNESS. The workflow does not run at all:
# no label, no gate comment, and NO RED CHECK. Nothing says "your workflow is broken" — the PR
# merely looks like it is waiting. A DEAD gate and a SLOW gate are indistinguishable from the
# outside, which is why this goes unnoticed.
#
# Same contract as lint_shell.sh / lint_yaml.sh / lint_sql.sh: RESOLVE, DON'T INSTALL. An
# optional linter must never trigger an install. Locally it skips with a warning when absent —
# a constrained box never hard-fails the commit flow. In CI the binary is installed with a
# pinned version and a verified SHA-256, and its absence FAILS (a graceful skip is right on a
# contributor's machine and is placebo in CI: a gate reporting its own blindness as OK). CI
# opts into that with LINT_ACTIONS_REQUIRED=1.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh" # resolve_python / resolve_poetry / run_poetry

bool_poetry_ok=false

resolve_actionlint_mode() {
	# Print "poetry" (a venv-vendored binary), "system" (a binary on PATH), or "" when absent.
	# Probes with --version so a real lint exit code is never mistaken for "absent".
	if [[ "$bool_poetry_ok" == true ]] && run_poetry run actionlint --version >/dev/null 2>&1; then
		printf 'poetry'
		return 0
	fi
	if command -v actionlint >/dev/null 2>&1; then
		printf 'system'
		return 0
	fi
	printf ''
}

discover_workflows() {
	# ⚠️ GROUP THE FIND EXPRESSION. `-name '*.yaml' -o -name '*.yml' -type f` parses as
	# `(-name '*.yaml') OR (-name '*.yml' AND -type f)` — `-o` binds looser than the implicit
	# `-a`, so `-type f` guards only the second branch and a DIRECTORY named `*.yaml` enters the
	# list and fails the gate for an unrelated reason. The \( … \) grouping is load-bearing.
	[ -d .github/workflows ] || return 0
	find .github/workflows \( -name '*.yaml' -o -name '*.yml' \) -type f | sort
}

main() {
	cd "$SCRIPT_DIR/.."

	mapfile -t list_workflows < <(discover_workflows)

	# ⚠️ FAIL WHEN DISCOVERY MATCHES ZERO FILES. actionlint exits 0 with no arguments, so a
	# wrapper whose glob matched nothing reports success FOREVER — the gate is green precisely
	# because it is checking nothing. Assert the count rather than trusting the exit code.
	if [ "${#list_workflows[@]}" -eq 0 ]; then
		if [ -d .github/workflows ]; then
			print_status "error" "no workflow files found under .github/workflows — actionlint would pass vacuously"
			return 1
		fi
		print_status "warning" "skip: no .github/workflows directory (offline scaffold)"
		return 0
	fi

	PYTHON="$(resolve_python 2>/dev/null)" || true
	export PYTHON
	if resolve_poetry; then
		bool_poetry_ok=true
	fi

	local str_mode
	str_mode="$(resolve_actionlint_mode)"
	if [ -z "$str_mode" ]; then
		if [ "${LINT_ACTIONS_REQUIRED:-0}" = "1" ]; then
			print_status "error" "actionlint is required here but absent — a skipped gate in CI is a gate reporting its own blindness as OK"
			return 1
		fi
		print_status "warning" "skip: actionlint absent (see the CI job, or install from https://github.com/rhysd/actionlint)"
		return 0
	fi

	# actionlint shells out to shellcheck for every `run:` block. Left unset, it applies that
	# tool's own defaults, which differ from the gate the rest of this repo is held to
	# (bin/CLAUDE.md) — so the same script would pass one gate and fail the other.
	# (A comment line may not START with the tool's name: it parses as a lint directive.)
	export SHELLCHECK_OPTS="--severity=warning --exclude=SC1091"

	print_status "info" "actionlint [$str_mode]: ${#list_workflows[@]} workflow(s)"
	if [ "$str_mode" = poetry ]; then
		run_poetry run actionlint "${list_workflows[@]}"
	else
		actionlint "${list_workflows[@]}"
	fi
	print_status "success" "actionlint OK"
}

main "$@"

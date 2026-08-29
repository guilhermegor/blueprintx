#!/usr/bin/env bash
# Resolve Poe the Poet by whichever invocation strategy works on THIS machine, then exec it
# with the passed arguments. The single Poe entrypoint for every hook, workflow and script —
# so nothing ever depends on a bare `poe` being on PATH.
#
# Why this exists — the same reason bin/poetry_exec.sh does, one layer up. Poe reaches a
# machine by three different routes, and which one is present is a property of the host, not
# of this project:
#
#   1. `poe` on PATH            — a pipx install, or an activated .venv that has it
#   2. `$PYTHON -m poethepoet`  — installed as a library but not on PATH (the Windows/Git Bash
#                                 case: the user-scripts dir is not on PATH, exactly as with
#                                 `pip install --user` Poetry)
#   3. `poetry poe`             — the Poetry plugin, IF someone installed it by hand
#
# ⚠️ The module is `poethepoet`, NOT `poe`: `python -m poe` fails with "No module named poe".
# That mistake costs a confusing minute every time, so it is spelled out here and in
# poe_tasks.toml rather than left to be rediscovered.
#
# ⚠️ Route 3 is LAST, and the project no longer declares the plugin at all. Three reasons, in
# order of how much they cost: declaring it via `[tool.poetry.requires-plugins]` BREAKS
# `poetry install` (a project-scoped plugin env keyed by project name, not path — measured);
# it is the slowest route (a full Poetry startup wraps every task); and poe's own docs advise
# against it for direct use, because Poetry's CLI framework mangles arbitrary task arguments
# and the plugin silently disappears if `--no-plugins` appears anywhere in the command line.
# It stays supported here because a hand-installed plugin costs this branch nothing.
#
# Usage: bash bin/poe_exec.sh <task> [task args...]
#   e.g. bash bin/poe_exec.sh lint
#        bash bin/poe_exec.sh test_feat some_keyword
#
# stdout discipline: all resolution status goes to stderr, so the task's own stdout passes
# through untouched and command substitution around this wrapper stays clean.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

# Populated by resolve_poe; the array form survives a multi-word invocation
# (`python -m poethepoet`) that a plain string would word-split wrongly.
POE_CMD=()

resolve_poe() {
	# The in-project venv FIRST, and this route is load-bearing rather than an optimisation.
	# poetry.toml forces `virtualenvs.in-project`, so after `poetry install` the project's own
	# pinned poe lives here — but `poetry install` does NOT put it on PATH, and $PYTHON is the
	# SYSTEM interpreter, so neither of the next two routes can see it. That is the exact
	# situation in CI (`poetry install --with dev`, then run a task from an unactivated shell),
	# where without this branch resolution would fall through to the plugin and fail on any host
	# that installed poe only as a dev-dep.
	local str_venv_poe
	for str_venv_poe in "${PROJECT_ROOT:-.}/.venv/bin/poe" "${PROJECT_ROOT:-.}/.venv/Scripts/poe.exe"; do
		if [[ -x "$str_venv_poe" ]]; then
			POE_CMD=("$str_venv_poe")
			print_status "debug" "Poe resolved: $str_venv_poe (in-project venv)"
			return 0
		fi
	done

	if command -v poe >/dev/null 2>&1; then
		POE_CMD=(poe)
		print_status "debug" "Poe resolved: poe (on PATH)"
		return 0
	fi

	# Probe by running the module, not by testing for a file: a `pip install --user` layout
	# puts the package where the interpreter finds it but the console script nowhere useful.
	if [[ -n "${PYTHON:-}" ]] && "$PYTHON" -m poethepoet --version >/dev/null 2>&1; then
		POE_CMD=("$PYTHON" -m poethepoet)
		print_status "debug" "Poe resolved: $PYTHON -m poethepoet"
		return 0
	fi

	if bash "$SCRIPT_DIR/poetry_exec.sh" poe --help >/dev/null 2>&1; then
		POE_CMD=(bash "$SCRIPT_DIR/poetry_exec.sh" poe)
		print_status "debug" "Poe resolved: poetry poe (Poetry plugin)"
		return 0
	fi

	return 1
}

report_unresolved() {
	print_status "error" "Poe the Poet could not be resolved on this machine."
	print_status "info" "Install it by any ONE of these routes:"
	print_status "info" "  bash bin/venv.sh                             # usual fix: build the venv"
	print_status "info" "  pipx install poethepoet                      # standalone, on PATH"
	print_status "info" "  poetry self add 'poethepoet[poetry_plugin]'  # optional Poetry plugin"
	print_status "info" "Poe is a dev dependency, so 'bash bin/venv.sh' (or 'poetry install"
	print_status "info" "--with dev') normally supplies it at .venv/bin/poe."
}

main() {
	# NOTE: zero arguments is valid and is the help path — bare `poe` prints the task list
	# built from the `help =` fields in poe_tasks.toml. This wrapper must not reject it, or
	# `bash bin/poe_exec.sh` would be the one route that cannot answer "what can I run?".

	# Route the resolution phase's stdout to stderr so a caller capturing the task's output
	# is never polluted by resolution chatter.
	{
		bootstrap_init
		wire_corporate_ca
	} 1>&2

	if ! resolve_poe 1>&2; then
		report_unresolved
		return 1
	fi

	exec "${POE_CMD[@]}" "$@"
}

main "$@"

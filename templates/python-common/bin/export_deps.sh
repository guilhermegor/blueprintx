#!/usr/bin/env bash
# Export the locked dependency set to requirements-lock.txt, for hosts that can run
# `pip install -r` but not Poetry — locked-down corporate boxes, slim containers, air-gapped
# transfers. This is the reason the plugin exists here at all.
#
# `export` is a PLUGIN subcommand, not core Poetry. So the question is never "is Poetry
# installed?" but "does the Poetry that RESOLVES HERE carry the plugin?" — and those two come
# apart silently, because a `pip install --user` Poetry and the project venv's Poetry report
# the SAME `--version` while carrying different plugin sets. Every version probe agrees and the
# subcommand still does not exist. That is why the plugin is pinned in `requirements.txt` (what
# ensure_poetry installs from) and not only as a dev-dependency: a dev-dep reaches the project
# venv and nothing else, so the recipe works from an activated shell and fails from a VS Code
# task, from cron, from CI, and from the fresh offline host it exists to serve.
#
# Diagnostics: the export output is CAPTURED and re-printed on failure, never discarded. Do not
# `>/dev/null 2>&1` a command whose failure you then explain — the explanation becomes a guess
# about text you refused to read, and any remedy must name the RESOLVED binary
# (`${POETRY_CMD[*]}`), never a bare `poetry` that may not be the one that just failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

# Overridable so a test can redirect the artifact out of the project tree.
OUTPUT_FILE="${OUTPUT_FILE:-$PROJECT_ROOT/requirements-lock.txt}"

export_deps() {
	local path_out="$OUTPUT_FILE"
	local str_output
	local int_status

	print_status "info" "Exporting locked dependencies to ${path_out##*/} ..."
	set +e
	str_output="$(run_poetry export \
		--format requirements.txt \
		--output "$path_out" \
		--without-hashes 2>&1)"
	int_status=$?
	set -e

	if [[ "$int_status" -eq 0 ]]; then
		local int_lines
		int_lines="$(wc -l <"$path_out" | tr -d ' ')"
		print_status "success" "Wrote ${path_out##*/} ($int_lines requirement lines)"
		return 0
	fi

	print_status "error" "poetry export failed (exit $int_status). Poetry said:"
	printf '%s\n' "$str_output" >&2
	print_status "error" "Resolved Poetry: ${POETRY_CMD[*]}"
	print_status "error" "An 'unknown command' above means THAT Poetry lacks the export plugin"
	print_status "error" "(not that it is uninstalled). Add it to the same install:"
	print_status "error" "  ${POETRY_CMD[*]} self add poetry-plugin-export"
	return "$int_status"
}

main() {
	bootstrap_init
	wire_corporate_ca
	ensure_poetry
	export_deps
}

main "$@"

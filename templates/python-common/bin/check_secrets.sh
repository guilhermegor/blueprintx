#!/bin/bash
#
# check_secrets.sh — secret scanning via gitleaks (blueprintx#305, gitleaks slice).
#
# WHY GITLEAKS AND NOT ONLY GITGUARDIAN: GitGuardian (blueprintx#155/#286) is the hosted
# product, and BlueprintX's own `GITGUARDIAN_API_KEY` measurably fails auth (`Invalid
# GitGuardian API key`, exit 3) — live detection there has never been proven. Worse, this repo
# is PUBLIC: shipping that key into every scaffolded project would either hand strangers the
# maintainer's quota or ship every generated project red on arrival. gitleaks needs NO API key
# and NO account, so it becomes the DEFAULT scanner for generated projects; GitGuardian stays
# available for anyone who wants the hosted product. This is additive, not a replacement.
#
# ONE implementation: this file is the only copy. It is bulk-copied verbatim into every
# generated Python project (`cp -r templates/python-common/bin/.`, no copy-list entry needed),
# and BlueprintX's own root pre-commit hook + workflow invoke this SAME copy via `--root .` —
# the identical pattern check_complexity.sh and check_function_length.py already use.
#
# Config resolution is gitleaks' own: it looks for `.gitleaks.toml` (or `gitleaks.toml`) at the
# root of the target being scanned. BlueprintX ships one at its own repo root and one in
# templates/python-common/ (copied to every generated project's root as `.gitleaks.toml`,
# exactly like ruff.toml/mypy.ini), so no `--config` flag is needed here.
#
# Resolve, don't install: a missing gitleaks is a graceful skip on a contributor's box, and a
# hard failure only when GITLEAKS_REQUIRED=1 (CI sets it) — a skip in CI is a gate reporting
# its own blindness as OK.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

STR_ROOT="."

parse_args() {
	# Only --root is accepted, so BlueprintX can run THIS file over its own tree instead of
	# keeping a second copy (the treatment blueprintx#189 gave the function-length gate).
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--root)
			STR_ROOT="${2:-.}"
			shift 2
			;;
		*)
			print_status "error" "Unknown argument: $1 (only --root <dir> is accepted)"
			exit 2
			;;
		esac
	done
}

run_gitleaks() {
	# gitleaks exits 0 (clean) or 1 (leaks found) — both are DATA, so let it drive our exit.
	print_status "section" "Secret scan (gitleaks)"
	if gitleaks git "$STR_ROOT" --no-banner --redact -v; then
		print_status "success" "gitleaks: no leaks found"
		return 0
	fi
	print_status "error" "gitleaks found a potential secret (see output above). A confirmed false positive gets a narrow, reasoned entry in .gitleaks.toml — never remove [extend] useDefault."
	return 1
}

main() {
	parse_args "$@"

	if ! command -v gitleaks >/dev/null 2>&1; then
		if [[ "${GITLEAKS_REQUIRED:-0}" == "1" ]]; then
			print_status "error" "gitleaks is required here but absent — a skipped gate in CI is a gate reporting its own blindness as OK"
			exit 1
		fi
		print_status "warning" "skip: gitleaks not installed (https://github.com/gitleaks/gitleaks#installing)"
		exit 0
	fi

	run_gitleaks
}

main "$@"

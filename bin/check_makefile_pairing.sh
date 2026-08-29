#!/usr/bin/env bash
# Enforces the Makefile <-> tasks.sh <-> bin/help.sh pairing (blueprintx#241): every
# user-facing Makefile target must have a matching case branch in tasks.sh AND be listed
# in bin/help.sh's usage text.
#
# Root-repo-only by design: Makefile and tasks.sh exist ONLY at the BlueprintX repo root —
# not in templates/ and not in any generated project (poe_tasks.toml since #236) — so this
# gate lives at bin/, not templates/python-common/bin/, and never ships as part of a scaffold.
# It also lives outside bin/ci/ (in flight under #271) to avoid colliding with that rework;
# it is not part of the bin/ci/*.sh family that CI's scaffold_checks.yml jobs share with
# pre-commit, since it has nothing to do with templates or generated-project linting.
#
# Opt-out: a target preceded by a `# pairing:internal` comment line is exempt (e.g. a
# .PHONY helper that composes other targets but was never meant to be user-facing on its
# own). Add the marker directly above the target line.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAKEFILE="$REPO_ROOT/Makefile"
TASKS_SH="$REPO_ROOT/tasks.sh"
HELP_SH="$REPO_ROOT/bin/help.sh"

# Real Makefile target names: lines like "name:" or "name: deps" at column 0, skipping
# .PHONY declarations, pattern rules, and any target marked with the opt-out comment on
# the immediately preceding line.
list_makefile_targets() {
	local prev=""
	while IFS= read -r line; do
		if [[ "$line" =~ ^([A-Za-z0-9_-]+):([^=]|$) ]]; then
			local target="${BASH_REMATCH[1]}"
			if [[ "$target" != ".PHONY" ]] && [[ "$prev" != *"pairing:internal"* ]]; then
				echo "$target"
			fi
		fi
		prev="$line"
	done <"$MAKEFILE"
}

target_in_tasks_sh() {
	local target="$1" underscored="${1//-/_}"
	grep -qE "^[[:space:]]*(${target}|${underscored})(\||\))" "$TASKS_SH"
}

target_in_help_sh() {
	grep -qE "^[[:space:]]*${1}[[:space:]]" "$HELP_SH"
}

main() {
	local errors=0 checked=0 target

	while IFS= read -r target; do
		checked=$((checked + 1))
		if ! target_in_tasks_sh "$target"; then
			echo "ERROR: Makefile target '$target' has no case branch in tasks.sh" >&2
			errors=$((errors + 1))
		fi
		if ! target_in_help_sh "$target"; then
			echo "ERROR: Makefile target '$target' is not listed in bin/help.sh" >&2
			errors=$((errors + 1))
		fi
	done < <(list_makefile_targets)

	if [ "$errors" -gt 0 ]; then
		echo "check_makefile_pairing: $errors error(s) found across $checked target(s)." >&2
		exit 1
	fi

	echo "check_makefile_pairing: all $checked Makefile target(s) are paired in tasks.sh and bin/help.sh."
}

main "$@"

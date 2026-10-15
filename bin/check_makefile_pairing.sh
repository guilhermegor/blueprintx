#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAKEFILE="$REPO_ROOT/Makefile"
TASKS_SH="$REPO_ROOT/tasks.sh"
HELP_SH="$REPO_ROOT/bin/help.sh"

list_makefile_targets() {
	local prev=""
	while IFS= read -r line; do
		if [[ "$line" =~ ^([A-Za-z0-9_][A-Za-z0-9_\ -]*):([^=]|$) ]]; then
			local names="${BASH_REMATCH[1]}" target
			for target in $names; do
				if [[ "$target" != ".PHONY" ]] && ! [[ "$prev" =~ (^|[[:space:]])#[[:space:]]*pairing:internal([[:space:]]|$) ]]; then
					echo "$target"
				fi
			done
		fi
		prev="$line"
	done <"$MAKEFILE"
}

target_spellings() {
	local hyphened="${1//_/-}" underscored="${1//-/_}"
	printf '%s|%s' "$hyphened" "$underscored"
}

target_in_tasks_sh() {
	grep -qE "^[[:space:]]*($(target_spellings "$1"))(\||\))" "$TASKS_SH"
}

target_in_help_sh() {
	grep -qE "^[[:space:]]*($(target_spellings "$1"))[[:space:]]" "$HELP_SH"
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

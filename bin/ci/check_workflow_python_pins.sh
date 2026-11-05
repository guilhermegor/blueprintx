#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${PINS_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

AWK_SCAN='
FNR == 1 { in_list = 0; in_block = 0 }
{
	str_line = $0
	sub(/(^|[[:space:]])#.*$/, "", str_line)
	if (in_block) {
		match(str_line, /^[[:space:]]*/)
		if (str_line ~ /^[[:space:]]*$/ || RLENGTH > int_indent) { check(str_line); next }
		in_block = 0
	}
	if (in_list) {
		if (str_line ~ /^[[:space:]]*(-|$)/) { check(str_line); next }
		in_list = 0
	}
	if (match(str_line, /(^[[:space:]]*(-[[:space:]]+)?|[{,][[:space:]]*)python-version:/)) {
		str_rest = substr(str_line, RSTART + RLENGTH)
		match(str_line, /^[[:space:]]*/)
		int_indent = RLENGTH
		if (str_rest ~ /^[[:space:]]*[|>][-+]?[[:space:]]*$/) in_block = 1
		else if (str_rest ~ /^[[:space:]]*$/) in_list = 1
		else {
			if (str_rest ~ /^[[:space:]]*\[/) sub(/\].*$/, "", str_rest)
			else sub(/[,}].*$/, "", str_rest)
			check(str_rest)
		}
	}
}
function check(str_value) {
	if (str_value ~ /(^|[^A-Za-z0-9._-])[0-9]+\.[0-9]+\.[0-9]+/) print FILENAME ":" FNR ":" $0
}
'

main() {
	local -a list_files=()
	local str_hits
	local str_dir
	for str_dir in "$REPO_ROOT/.github/workflows" "$REPO_ROOT/templates"; do
		if [ ! -d "$str_dir" ]; then
			echo "Missing $str_dir; refusing a partial scan." >&2
			exit 1
		fi
	done
	local str_found
	str_found="$(mktemp)"
	find "$REPO_ROOT/.github/workflows" "$REPO_ROOT/templates" \
		-name node_modules -prune -o \
		-path '*/.github/workflows/*' \( -name '*.yml' -o -name '*.yaml' \) -print0 >"$str_found" || { rm -f "$str_found"; exit 1; }
	mapfile -d '' -t list_files <"$str_found"
	rm -f "$str_found"
	if [ "${#list_files[@]}" -eq 0 ]; then
		echo "No workflow files found under $REPO_ROOT; refusing to pass vacuously." >&2
		exit 1
	fi
	str_hits="$(awk "$AWK_SCAN" "${list_files[@]}")"
	if [ -n "$str_hits" ]; then
		echo "Patch-level python-version pin(s); pin the minor only (e.g. \"3.12\"):" >&2
		printf '%s\n' "$str_hits" | sed 's/^/    /' >&2
		exit 1
	fi
	echo "workflow python-version pins OK (minor-level only, ${#list_files[@]} files scanned)."
}

main "$@"

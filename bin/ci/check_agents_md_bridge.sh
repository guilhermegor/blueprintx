#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${BRIDGE_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

readonly -a ARR_SHIMS=(
	"Edit AGENTS.md, not this file. Claude-Code-only lines go below this one."
	"<!-- Edit AGENTS.md, not this file. Claude-Code-only lines go below this one. -->"
)

scaffold_text() {
	local str_dir="$1" str_scaffold
	str_scaffold="$(sed -n 's/^scaffold=//p' "$str_dir/skeleton.meta")"
	cat "$REPO_ROOT/$str_scaffold" "$REPO_ROOT"/bin/lib/scaffold_*.sh
}

source_exists() {
	local str_dir="$1" str_target="$2"
	[ -e "$str_dir/$str_target" ] || [ -e "$REPO_ROOT/templates/common/$str_target" ]
}

is_shim() {
	local str_line="$1" str_shim
	for str_shim in "${ARR_SHIMS[@]}"; do
		[ "$str_line" = "$str_shim" ] && return 0
	done
	return 1
}

check_bridge() {
	local str_dir="$1" str_name str_bridge str_text str_line str_target int_fail=0
	str_name="$(basename "$str_dir")"
	str_bridge="$str_dir/CLAUDE.md"
	str_text="$(scaffold_text "$str_dir")"

	while IFS= read -r str_line || [ -n "$str_line" ]; do
		if [ -z "$str_line" ] || is_shim "$str_line"; then
			continue
		fi
		if [[ "$str_line" =~ ^@[A-Za-z0-9_./-]+$ ]]; then
			str_target="${str_line#@}"
			if ! source_exists "$str_dir" "$str_target"; then
				echo "$str_name: CLAUDE.md imports @$str_target but no such source file exists" >&2
				int_fail=1
			elif ! grep -qF "/$str_target\"" <<<"$str_text"; then
				echo "$str_name: CLAUDE.md imports @$str_target but its scaffold never copies it" >&2
				int_fail=1
			fi
			continue
		fi
		echo "$str_name: CLAUDE.md bridge holds a line outside the allowlist: $str_line" >&2
		int_fail=1
	done <"$str_bridge"
	return "$int_fail"
}

main() {
	local str_meta str_dir int_fail=0 int_count=0
	for str_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
		str_dir="$(dirname "$str_meta")"
		[ -f "$str_dir/CLAUDE.md" ] || continue
		int_count=$((int_count + 1))
		check_bridge "$str_dir" || int_fail=1
	done
	if [ "$int_fail" -ne 0 ]; then
		exit 1
	fi
	echo "CLAUDE.md bridges OK ($int_count skeletons)."
}

main "$@"

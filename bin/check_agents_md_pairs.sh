#!/bin/bash

set -euo pipefail

readonly STR_MARKER="Edit AGENTS.md, not this file. Claude-Code-only lines go below this one."
readonly STR_MARKER_HTML="<!-- $STR_MARKER -->"

fail() {
	echo "check_agents_md_pairs: $1" >&2
	int_fail=1
}

sibling_agents() {
	local str_dir str_base
	str_dir="$(dirname "$1")"
	str_base="$(basename "$1")"
	printf '%s/%s' "$str_dir" "${str_base/CLAUDE/AGENTS}"
}

check_file() {
	local str_file="$1" str_agents str_line str_first int_seen=0
	str_agents="$(sibling_agents "$str_file")"
	[ -f "$str_agents" ] || fail "$str_file has no sibling $(basename "$str_agents")"
	[ ! -f "$str_agents" ] || [ -r "$str_agents" ] || fail "$str_file has an unreadable sibling $(basename "$str_agents")"
	[ -r "$str_file" ] || {
		fail "$str_file is unreadable"
		return
	}
	IFS= read -r str_first <"$str_file" || true
	[ "$str_first" = "@AGENTS.md" ] || fail "$str_file does not start with @AGENTS.md"
	while IFS= read -r str_line || [ -n "$str_line" ]; do
		if [ "$str_line" = "$STR_MARKER" ] || [ "$str_line" = "$STR_MARKER_HTML" ]; then
			int_seen=1
			break
		fi
		[ -z "$str_line" ] || [ "$str_line" = "@AGENTS.md" ] && continue
		if [[ "$str_line" =~ ^@[A-Za-z0-9_./-]+$ ]]; then
			[ -e "$(dirname "$str_file")/${str_line#@}" ] || fail "$str_file imports $str_line but no such file exists"
			continue
		fi
		fail "$str_file holds a non-import line above the marker: $str_line"
	done <"$str_file"
	[ "$int_seen" -eq 1 ] || fail "$str_file lacks the marker line"
}

discover() {
	find "$1" \( -name .git -o -name .claude -o -name node_modules -o -name .venv -o -name .mypy_cache \) -prune \
		-o \( -name 'CLAUDE.md' -o -name '*_CLAUDE.md' \) -type f -print | sort
}

main() {
	local str_root="." int_fail=0 int_count=0 str_file
	local -a arr_files=()
	while [ "$#" -gt 0 ]; do
		case "$1" in
		--root)
			[ "$#" -ge 2 ] || {
				echo "check_agents_md_pairs: --root needs a directory" >&2
				exit 2
			}
			str_root="$2"
			shift 2
			;;
		*)
			arr_files+=("$1")
			shift
			;;
		esac
	done
	if [ "${#arr_files[@]}" -eq 0 ]; then
		[ -d "$str_root" ] || {
			echo "check_agents_md_pairs: $str_root is not a directory" >&2
			exit 2
		}
		local str_found
		str_found="$(discover "$str_root")" || {
			echo "check_agents_md_pairs: discovery under $str_root failed; refusing a partial scan" >&2
			exit 2
		}
		[ -z "$str_found" ] || mapfile -t arr_files <<<"$str_found"
	fi
	for str_file in "${arr_files[@]}"; do
		int_count=$((int_count + 1))
		check_file "$str_file"
	done
	if [ "$int_count" -eq 0 ]; then
		echo "check_agents_md_pairs: no CLAUDE.md found; the gate checked nothing" >&2
		exit 1
	fi
	[ "$int_fail" -eq 0 ] || exit 1
	echo "AGENTS.md pairs OK ($int_count CLAUDE.md files)."
}

main "$@"

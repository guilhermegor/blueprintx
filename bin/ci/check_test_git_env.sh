#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
if [ "${1:-}" = "--root" ]; then
	[ -n "${2:-}" ] && [ -d "$2" ] || {
		print_status "error" "--root needs an existing directory (got '${2:-}')"
		exit 2
	}
	REPO_ROOT="$(cd "$2" && pwd)"
	shift 2
fi
[ "$#" -eq 0 ] || {
	print_status "error" "unexpected argument '$1' (usage: check_test_git_env.sh [--root <dir>])"
	exit 2
}

re_spawn='(^|[^[:alnum:]_./-])git([[:space:]]+-[cC][[:space:]]+[^[:space:]]+)*[[:space:]]+(init|commit|add|rm|mv|reset|checkout|switch|restore|merge|rebase|cherry-pick|tag|stash|update-ref|update-index|am|apply)\b|(bash|sh|source) +"?[^ ]*bin/scaffold/|^[[:space:]]*("[^ =]*|[^ ="]*)bin/scaffold/[^ ]+\.sh'

logical_lines() {
	awk '
		/^[[:space:]]*#/ && str_pending == "" { next }
		/\\$/ { str_pending = str_pending substr($0, 1, length($0) - 1) " "; next }
		{ print str_pending $0; str_pending = "" }
		END { if (str_pending != "") print str_pending }
	' "$1"
}

first_clear_line() {
	logical_lines "$1" | awk '
		{ n++ }
		int_found || !/(^|[;&|({]|then|do|else)[[:space:]]*unset[[:space:]]/ { next }
		/compgen -e *[|] *grep .\^GIT_/ { int_found = n }
		/GIT_DIR/ && /GIT_INDEX_FILE/ && /GIT_WORK_TREE/ { int_found = n }
		END { if (int_found) print int_found }
	'
}

errors=0
checked=0
shopt -s nullglob
for path_test in "$REPO_ROOT"/tests/*.sh; do
	checked=$((checked + 1))
	int_spawn="$(logical_lines "$path_test" | grep -nE "$re_spawn" | head -n 1 | cut -d: -f1 || true)"
	[ -n "$int_spawn" ] || continue
	int_clear="$(first_clear_line "$path_test")"
	if [ -z "$int_clear" ] || [ "$int_clear" -gt "$int_spawn" ]; then
		print_status "error" "tests/$(basename "$path_test") — spawns git or a scaffold (code line $int_spawn) without first clearing the inherited GIT_* env; under pre-commit, GIT_DIR and GIT_INDEX_FILE point at the calling repository, so its commits land there. Add: while IFS= read -r str_var; do unset \"\$str_var\"; done < <(compgen -e | grep '^GIT_')"
		errors=$((errors + 1))
	fi
done

if [ "$checked" -eq 0 ]; then
	print_status "error" "no tests/*.sh found under $REPO_ROOT — broken check, not a clean one"
	exit 1
fi

if [ "$errors" -gt 0 ]; then
	print_status "error" "check_test_git_env: $errors error(s) found."
	exit 1
fi

print_status "success" "check_test_git_env: every git-spawning test clears GIT_* ($checked tests checked)."

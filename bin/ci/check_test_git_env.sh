#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ "${1:-}" = "--root" ]; then
	[ -n "${2:-}" ] && [ -d "$2" ] || {
		echo "ERROR: --root needs an existing directory (got '${2:-}')" >&2
		exit 2
	}
	REPO_ROOT="$(cd "$2" && pwd)"
	shift 2
fi
[ "$#" -eq 0 ] || {
	echo "ERROR: unexpected argument '$1' (usage: check_test_git_env.sh [--root <dir>])" >&2
	exit 2
}

re_spawn='(^|[^[:alnum:]_./-])git( +-C +[^ ]+)? +(init|commit)\b|(bash|sh|source) +"?[^ ]*bin/scaffold/|^[[:space:]]*("[^ =]*|[^ ="]*)bin/scaffold/[^ ]+\.sh'
re_clear="unset[^#]*GIT_DIR[^#]*GIT_INDEX_FILE|unset[^#]*GIT_INDEX_FILE[^#]*GIT_DIR|grep '\\^GIT_'|env +-u +GIT_DIR"

errors=0
checked=0
shopt -s nullglob
for path_test in "$REPO_ROOT"/tests/*.sh; do
	checked=$((checked + 1))
	int_spawn="$(grep -vE '^[[:space:]]*#' "$path_test" | grep -nE "$re_spawn" | head -n 1 | cut -d: -f1 || true)"
	[ -n "$int_spawn" ] || continue
	int_clear="$(grep -vE '^[[:space:]]*#' "$path_test" | grep -nE "$re_clear" | head -n 1 | cut -d: -f1 || true)"
	if [ -z "$int_clear" ] || [ "$int_clear" -gt "$int_spawn" ]; then
		echo "ERROR: tests/$(basename "$path_test") — spawns git or a scaffold (code line $int_spawn)" \
			"without first clearing the inherited GIT_* env; under pre-commit, GIT_DIR and" \
			"GIT_INDEX_FILE point at the calling repository, so its commits land there." \
			"Add: while IFS= read -r str_var; do unset \"\$str_var\"; done < <(compgen -e | grep '^GIT_')" >&2
		errors=$((errors + 1))
	fi
done

if [ "$checked" -eq 0 ]; then
	echo "ERROR: no tests/*.sh found under $REPO_ROOT — broken check, not a clean one" >&2
	exit 1
fi

if [ "$errors" -gt 0 ]; then
	echo "check_test_git_env: $errors error(s) found." >&2
	exit 1
fi

echo "check_test_git_env: every git-spawning test clears GIT_* ($checked tests checked)."

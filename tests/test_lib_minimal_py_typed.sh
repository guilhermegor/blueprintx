#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCAFFOLD="$REPO_ROOT/bin/scaffold/python_lib_minimal.sh"
PYPROJECT="$REPO_ROOT/templates/lib-minimal/pyproject.toml"
int_failures=0

check() {
	local str_name="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		echo "ok: $str_name"
	else
		echo "FAIL: $str_name"
		int_failures=$((int_failures + 1))
	fi
}

check "scaffold copies py.typed into the package" \
	grep -qF 'templates/lib-minimal/py.typed" "$project_path/src/$PROJECT_PKG_NAME/py.typed"' "$SCAFFOLD"
check "template py.typed is an empty file" test -f "$REPO_ROOT/templates/lib-minimal/py.typed" -a ! -s "$REPO_ROOT/templates/lib-minimal/py.typed"

str_main="$(sed -n '/^main() {/,/^}/p' "$SCAFFOLD")"
int_commit="$(grep -n 'commit_online_artifacts "\$PROJECT_PATH"' <<<"$str_main" | head -1 | cut -d: -f1)"
int_protect="$(grep -n 'apply_branch_protection "\$PROJECT_PATH"' <<<"$str_main" | head -1 | cut -d: -f1)"
int_lock="$(grep -n 'lib_minimal_lock_dependencies' <<<"$str_main" | tail -1 | cut -d: -f1)"
check "versioning commit is pushed before main is protected" test -n "$int_commit" -a -n "$int_protect" -a "${int_commit:-0}" -lt "${int_protect:-0}"
check "poetry.lock is generated before the online commit" test -n "$int_lock" -a "${int_lock:-99}" -lt "${int_commit:-0}"
check "prompt_git_remote_setup no longer protects main" bash -c '! sed -n "/^prompt_git_remote_setup() {/,/^}/p" "$1" | grep -q apply_branch_protection' _ "$SCAFFOLD"

TESTS_YAML="$REPO_ROOT/templates/python-common/.github/workflows/tests.yml"
str_matrix="$(grep -m1 'python-version: \[' "$TESTS_YAML" | grep -oE '3\.[0-9]+' | sort -V | tr '\n' ' ')"
str_classifiers="$(grep -oE 'Programming Language :: Python :: 3\.[0-9]+' "$PYPROJECT" | grep -oE '3\.[0-9]+' | sort -V | tr '\n' ' ')"
str_floor="$(grep -m1 '^python = ' "$PYPROJECT" | grep -oE '3\.[0-9]+' | head -1)"

check "tests.yml matrix was read" test -n "$str_matrix"
check "classifiers match the tests.yml matrix ($str_matrix)" test "$str_classifiers" = "$str_matrix"
check "requires-python floor ($str_floor) equals the lowest matrix version" test "$str_floor" = "${str_matrix%% *}"

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"

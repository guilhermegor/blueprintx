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

TESTS_YAML="$REPO_ROOT/templates/python-common/.github/workflows/tests.yaml"
str_matrix="$(grep -m1 'python-version: \[' "$TESTS_YAML" | grep -oE '3\.[0-9]+' | sort -V | tr '\n' ' ')"
str_classifiers="$(grep -oE 'Programming Language :: Python :: 3\.[0-9]+' "$PYPROJECT" | grep -oE '3\.[0-9]+' | sort -V | tr '\n' ' ')"
str_floor="$(grep -m1 '^python = ' "$PYPROJECT" | grep -oE '3\.[0-9]+' | head -1)"

check "tests.yaml matrix was read" test -n "$str_matrix"
check "classifiers match the tests.yaml matrix ($str_matrix)" test "$str_classifiers" = "$str_matrix"
check "requires-python floor ($str_floor) equals the lowest matrix version" test "$str_floor" = "${str_matrix%% *}"

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"

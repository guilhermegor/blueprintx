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

for str_minor in 10 11 12 13 14; do
	check "classifier for Python 3.$str_minor present" \
		grep -qF "\"Programming Language :: Python :: 3.$str_minor\"" "$PYPROJECT"
done

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"

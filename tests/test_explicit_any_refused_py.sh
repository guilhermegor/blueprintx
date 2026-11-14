#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKELETON="${1:-lib-minimal}"
# shellcheck source=bin/lib/spec.sh
source "$REPO_ROOT/bin/lib/spec.sh"
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

str_scaffold_rel="$(grep '^scaffold=' "$REPO_ROOT/templates/$SKELETON/skeleton.meta" | cut -d= -f2-)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PROJECT_PATH="$WORK_DIR/ci-scaffold"

source "$REPO_ROOT/bin/lib/no_background_git.sh"
spec_stdin_for_skeleton "$SKELETON" "" |
	BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot LINKEDIN_URL=https://www.linkedin.com/in/ci-bot \
		bash "$REPO_ROOT/$str_scaffold_rel" "$WORK_DIR" ci-scaffold "explicit any probe" "0.0.1" >"$WORK_DIR/scaffold.log" 2>&1 ||
	{ cat "$WORK_DIR/scaffold.log"; echo "FAIL: scaffold exited non-zero"; exit 1; }
cd "$PROJECT_PATH" || exit 1
poetry install --with dev --no-interaction --no-ansi >"$WORK_DIR/install.log" 2>&1 ||
	{ cat "$WORK_DIR/install.log"; echo "FAIL: poetry install exited non-zero"; exit 1; }

run_mypy() {
	(cd "$PROJECT_PATH/src" && poetry run mypy --config-file ../mypy.ini . 2>&1)
}

check "mypy.ini sets disallow_any_explicit = True" grep -qx 'disallow_any_explicit = True' mypy.ini
if str_clean_out="$(run_mypy)"; then
	echo "ok: the freshly generated tree passes mypy"
else
	echo "FAIL: the freshly generated tree passes mypy"
	echo "$str_clean_out"
	int_failures=$((int_failures + 1))
fi

str_pkg_dir="$(find "$PROJECT_PATH/src" -mindepth 1 -maxdepth 1 -type d -name 'ci_scaffold' | head -n 1)"
str_plant_dir="${str_pkg_dir:-$PROJECT_PATH/src}"
cat >"$str_plant_dir/planted_any.py" <<'PY'
"""Probe module: a nested explicit Any that ruff's ANN401 cannot see."""

from collections.abc import Callable
from typing import Any


def build(fn_builder: Callable[[Any, str], list[str]]) -> list[str]:
    """Call the builder.

    Parameters
    ----------
    fn_builder : Callable[[Any, str], list[str]]
        A builder.

    Returns
    -------
    list[str]
        Its result.
    """
    return fn_builder(None, "x")
PY

str_out="$(run_mypy)"
int_rc=$?
if [ "$int_rc" -ne 0 ] && grep -q 'planted_any.py.*\[explicit-any\]' <<<"$str_out"; then
	echo "ok: a nested explicit Any outside the exemptions is refused by mypy"
else
	echo "FAIL: mypy accepted a nested explicit Any (exit $int_rc)"
	echo "$str_out"
	int_failures=$((int_failures + 1))
fi

if [ -f "$PROJECT_PATH/src/controller/_pipeline.py" ]; then
	rm -f "$str_plant_dir/planted_any.py"
	printf '\nfrom typing import Any\n\n\ndef planted(x: list[Any]) -> int:\n    """Probe."""\n    return len(x)\n' \
		>>"$PROJECT_PATH/src/controller/_pipeline.py"
	str_out="$(run_mypy)"
	int_rc=$?
	if [ "$int_rc" -ne 0 ] && grep -q 'controller/_pipeline.py.*\[explicit-any\]' <<<"$str_out"; then
		echo "ok: an explicit Any in controller/_pipeline.py is refused (blueprintx#1030)"
	else
		echo "FAIL: mypy accepted an explicit Any in controller/_pipeline.py (exit $int_rc)"
		echo "$str_out"
		int_failures=$((int_failures + 1))
	fi
fi

[ "$int_failures" -eq 0 ] || {
	echo "$int_failures case(s) failed"
	exit 1
}
echo "all cases passed"

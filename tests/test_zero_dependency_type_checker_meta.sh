#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')
export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
    echo "FAIL ($1): $2"
    int_failures=$((int_failures + 1))
}

scaffold_zero_dependency() {
    local file="$WORK_DIR/zero-dep.spec" str_out
    printf 'project_name=spec-probe\nproject_description=probe\nlanguage=python\n' >"$file"
    printf 'skeleton=lib-minimal\nlicense=MIT\ngithub_username=ci-bot\ndocs_locale=en\n' >>"$file"
    printf 'zero_dependency=y\n' >>"$file"
    str_out="$(cd "$WORK_DIR" && TMPDIR="$WORK_DIR" bash "$REPO_ROOT/bin/blueprintx.sh" new --spec "$file" --dev 2>&1 </dev/null)"
    sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$str_out" | sed 's/\x1b\[[0-9;]*m//g' | tail -1
}

write_probe() {
    local path_probe="$1" str_meta="$2"
    cat >"$path_probe" <<PY
"""Probe class for the zero-dependency TypeChecker test."""

from spec_probe._internal.utils.typing import TypeChecker


class Probe${str_meta:+(metaclass=TypeChecker)}:
    """Probe subject."""

PY
    write_probe_methods >>"$path_probe"
}

write_probe_methods() {
    cat <<'PY'
    def __init__(self) -> None:
        self._int_base = 10

    def add(self, *, value: int) -> int:
        """Add ``value`` to the base.

        Parameters
        ----------
        value : int
            The addend.

        Returns
        -------
        int
            The base plus ``value``.
        """
        return self._int_base + value

    @staticmethod
    def double(*, value: int) -> int:
        """Return twice ``value``.

        Parameters
        ----------
        value : int
            The number.

        Returns
        -------
        int
            Twice ``value``.
        """
        return value * 2

    @classmethod
    def triple(cls, *, value: int) -> int:
        """Return three times ``value``.

        Parameters
        ----------
        value : int
            The number.

        Returns
        -------
        int
            Three times ``value``.
        """
        return value * 3
PY
}

test_class_without_metaclass_fails_check_typing() {
    local path_proj="$1"
    write_probe "$path_proj/src/spec_probe/probe.py" ""
    if (cd "$path_proj" && python3 bin/check_typing.py >/dev/null 2>&1); then
        fail "should-fail" "check_typing passed a root class with no metaclass"
    else
        pass "check_typing rejects a zero-dependency class without metaclass=TypeChecker"
    fi
}

test_class_with_metaclass_passes_and_checks_arguments() {
    local path_proj="$1" str_out
    write_probe "$path_proj/src/spec_probe/probe.py" "y"
    if ! (cd "$path_proj" && python3 bin/check_typing.py >/dev/null 2>&1); then
        fail "should-pass" "check_typing rejected a class declaring metaclass=TypeChecker"
        return
    fi
    str_out="$(cd "$path_proj" && PYTHONPATH=src python3 -c '
from spec_probe.probe import Probe
assert Probe().add(value=1) == 11
assert Probe.double(value=2) == 4
assert Probe.triple(value=2) == 6
for fn in (Probe().add, Probe.double, Probe.triple):
    try:
        fn(value="1")
    except TypeError:
        print("TypeError")
' 2>&1)"
    if [ "$str_out" = "$(printf "TypeError\nTypeError\nTypeError")" ]; then
        pass "metaclass-wrapped method accepts good arguments and raises TypeError on a wrong one (instance, static and class methods)"
    else
        fail "runtime check" "got: $str_out"
    fi
}

main() {
    local path_proj
    path_proj="$(scaffold_zero_dependency)/spec-probe"
    if [ ! -f "$path_proj/src/spec_probe/_internal/utils/typing/type_checker_meta.py" ]; then
        fail "scaffold" "type_checker_meta.py missing from the zero-dependency scaffold at $path_proj"
        exit 1
    fi
    test_class_without_metaclass_fails_check_typing "$path_proj"
    test_class_with_metaclass_passes_and_checks_arguments "$path_proj"
    if [ "$int_failures" -eq 0 ]; then
        echo "All zero-dependency TypeChecker tests passed."
        exit 0
    fi
    echo "$int_failures zero-dependency TypeChecker test(s) FAILED."
    exit 1
}

main

#!/bin/bash

set -euo pipefail

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0
FIXTURES="$REPO_ROOT/tests/fixtures/test_git_env"

expect_gate() {
    local str_fixture="$1" str_want="$2" str_root str_got="pass" str_out
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/tests"
    cp "$FIXTURES/$str_fixture.txt" "$str_root/tests/test_sample.sh"
    str_out="$(bash "$REPO_ROOT/bin/ci/check_test_git_env.sh" --root "$str_root" 2>&1)" || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_fixture -> $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ "$str_want" = "fail" ] && ! printf '%s' "$str_out" | grep -qF "without first clearing"; then
        print_status "error" "$str_fixture -> failed, but never explained why"
        int_failures=$((int_failures + 1))
    fi
}

expect_gate cleared_git pass
expect_gate cleared_scaffold pass
expect_gate no_spawn pass
expect_gate uncleared_git_init fail
expect_gate uncleared_git_commit fail
expect_gate uncleared_scaffold fail
expect_gate clear_after_spawn fail
expect_gate uncleared_git_dash_c fail
expect_gate grep_without_unset fail

str_empty="$(mktemp -d)"
if bash "$REPO_ROOT/bin/ci/check_test_git_env.sh" --root "$str_empty" >/dev/null 2>&1; then
    print_status "error" "empty root passed (a gate that checked nothing)"
    int_failures=$((int_failures + 1))
fi
rm -rf "$str_empty"

if ! bash "$REPO_ROOT/bin/ci/check_test_git_env.sh" >/dev/null 2>&1; then
    print_status "error" "the real tests/ tree fails the gate"
    int_failures=$((int_failures + 1))
fi

if [ "$int_failures" -gt 0 ]; then
    print_status "error" "$int_failures check(s) failed"
    exit 1
fi
print_status "success" "check_test_git_env: all checks passed"

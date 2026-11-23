#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

if ! command -v timeout >/dev/null 2>&1; then
    print_status "warning" "SKIP: timeout not on PATH, closed-stdin suite not run"
    exit 0
fi

int_failures=0

fail() {
    print_status "error" "FAIL: $1"
    int_failures=$((int_failures + 1))
}

pass() {
    print_status "success" "PASS: $1"
}

expect_closed_stdin_exit() {
    local str_prompt="$1" str_label="$2" str_out int_rc=0
    str_out="$(
        timeout 5 bash -c '
            str_root="$1"
            str_fn="$2"
            set --
            source "$str_root/bin/blueprintx.sh"
            if [ "$str_fn" = prompt_skeleton ]; then
                prompt_skeleton python
            else
                "$str_fn"
            fi
        ' _ "$REPO_ROOT" "$str_prompt" </dev/null 2>&1
    )" || int_rc=$?
    if [ "$int_rc" -eq 0 ] || [ "$int_rc" -eq 124 ]; then
        fail "$str_prompt on closed stdin -> exit $int_rc (expected non-zero, not a timeout)"
    elif [ "$(grep -c "stdin closed at $str_label" <<<"$str_out")" -ne 1 ]; then
        fail "$str_prompt -> expected one 'stdin closed at $str_label' message"
    else
        pass "$str_prompt on closed stdin exits $int_rc with one message"
    fi
}

expect_closed_stdin_exit prompt_language "language prompt"
expect_closed_stdin_exit prompt_skeleton "skeleton prompt"

expect_eof_default() {
    local str_fn="$1" str_want="$2" str_got int_rc=0
    str_got="$(timeout 5 bash -c 'str_root="$1"; str_fn="$2"; set --; source "$str_root/bin/blueprintx.sh"; "$str_fn"' _ "$REPO_ROOT" "$str_fn" </dev/null 2>/dev/null)" || int_rc=$?
    if [ "$int_rc" -eq 0 ] && [ "$str_got" = "$str_want" ]; then
        pass "$str_fn on closed stdin takes the default ($str_want)"
    else
        fail "$str_fn on closed stdin -> exit $int_rc, got '$str_got', expected default '$str_want'"
    fi
}

expect_eof_default prompt_license MIT
expect_eof_default prompt_docs_locale en

str_partial="$(printf '2' | timeout 5 bash -c 'str_root="$1"; set --; source "$str_root/bin/blueprintx.sh"; prompt_license' _ "$REPO_ROOT" 2>/dev/null)" || int_partial_rc=$?
if [ "${int_partial_rc:-0}" -eq 0 ] && [ "$str_partial" = "Apache-2.0" ]; then
    pass "prompt_license accepts a final answer with no trailing newline"
else
    fail "prompt_license on '2' without newline -> exit ${int_partial_rc:-0}, got '$str_partial', expected Apache-2.0"
fi

[ "$int_failures" -eq 0 ] || exit 1

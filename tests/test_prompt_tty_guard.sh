#!/bin/bash
# Should-fail tests for the non-terminal-stdin guard on scaffold prompts (blueprintx#539).
#
# `read` consumes a piped stdin happily, so a stray line left on a pipe answered a question
# nobody asked. Two legs: the helpers behave (a piped "y" is not an answer unless the
# harness opted in), and no scaffold script reads stdin without going through them.
#
# Usage: bash tests/test_prompt_tty_guard.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

fail() {
    print_status "error" "FAIL: $1"
    int_failures=$((int_failures + 1))
}

pass() {
    print_status "success" "PASS: $1"
}

# expect <label> <want> <got>
expect() {
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (want '$2', got '$3')"; fi
}

# Runs prompt_yes_no under a piped stdin (never a terminal here) and prints the result.
# $1 = stdin line, $2 = default, $3 = BLUEPRINTX_STDIN_ANSWERS value (may be empty).
run_yes_no() {
    printf '%s\n' "$1" | BLUEPRINTX_STDIN_ANSWERS="$3" bash -c '
        source "$1/bin/lib/common.sh"
        prompt_yes_no ANSWER "q? " "$2" >/dev/null
        echo "$ANSWER"' _ "$REPO_ROOT" "$2"
}

expect "piped y does not enable an opt-in (default n)" "false" "$(run_yes_no y n "")"
expect "piped n does not flip a safe-yes prompt (default y)" "true" "$(run_yes_no n y "")"
expect "opted-in feed: piped y answers" "true" "$(run_yes_no y n 1)"
expect "opted-in feed: piped n answers" "false" "$(run_yes_no n y 1)"

str_text="$(printf 'stray\n' | BLUEPRINTX_STDIN_ANSWERS="" bash -c '
    source "$1/bin/lib/common.sh"
    prompt_read ANSWER "q? " >/dev/null
    echo "[$ANSWER]"' _ "$REPO_ROOT")"
expect "prompt_read leaves a piped line unread" "[]" "$str_text"

# Static leg: any bare `read` prompt in a scaffold or its libs must sit directly under a
# prompt_can_read guard. `while ... read` loops over files are not prompts.
str_bare="$(
    cd "$REPO_ROOT"
    grep -nE '^[[:space:]]*read( -[a-zA-Z]+)* ' bin/scaffold/*.sh bin/lib/scaffold_*.sh \
        | grep -vE 'while|IFS=' || true
)"
while IFS= read -r str_line; do
    [ -n "$str_line" ] || continue
    str_file="${str_line%%:*}"
    str_rest="${str_line#*:}"
    int_no="${str_rest%%:*}"
    if ! sed -n "$((int_no - 1))p" "$REPO_ROOT/$str_file" | grep -q 'prompt_can_read'; then
        fail "unguarded stdin read: $str_line"
    fi
done <<<"$str_bare"
pass "static scan of bin/scaffold and bin/lib/scaffold_*.sh complete"

if [ "$int_failures" -gt 0 ]; then
    print_status "error" "$int_failures failure(s)"
    exit 1
fi
print_status "success" "all prompt tty-guard tests passed"

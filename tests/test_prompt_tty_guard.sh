#!/bin/bash

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

expect() {
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (want '$2', got '$3')"; fi
}

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

run_streams() {
    local str_err_file
    str_err_file="$(mktemp)"
    local str_out
    str_out="$(printf 'y\n' | BLUEPRINTX_STDIN_ANSWERS="$1" bash -c '
        source "$1/bin/lib/common.sh"
        prompt_yes_no ANSWER "$(prompt_main "Create GitHub repo? [y/N]: ")" n
        echo "$ANSWER"' _ "$REPO_ROOT" 2>"$str_err_file")"
    printf '%s|%s' "$str_out" "$(cat "$str_err_file")"
    rm -f "$str_err_file"
}

str_unset="$(run_streams "")"
expect "no opt-in: stdout carries only the answer" "false" "${str_unset%%|*}"
expect "no opt-in: warning names the prompt and the default on stderr" \
    "stdin is not a terminal; using 'n' for \"[?] Create GitHub repo?\" (set BLUEPRINTX_STDIN_ANSWERS=1 to answer from stdin)" \
    "${str_unset#*|}"
str_set="$(run_streams 1)"
expect "opted-in: stdout carries the piped answer" "true" "${str_set%%|*}"
expect "opted-in: no warning on stderr" "" "${str_set#*|}"

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

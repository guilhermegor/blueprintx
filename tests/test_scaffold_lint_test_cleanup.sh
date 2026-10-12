#!/bin/bash
# Should-fail tests for scaffold_lint_test.sh cleanup (blueprintx#762): a failing rm in the
# EXIT trap must not replace the test's own exit status, and git must not auto-gc.
#
# Usage: bash tests/test_scaffold_lint_test_cleanup.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${1:-$REPO_ROOT/bin/ci/scaffold_lint_test.sh}"
int_failures=0

check() {
    if [ "$2" = "$3" ]; then
        echo "PASS: $1"
    else
        echo "FAIL: $1 (want '$2', got '$3')"
        int_failures=$((int_failures + 1))
    fi
}

str_def="$(sed -n '/^cleanup() {/,/^}/p' "$SCRIPT")"
[ -n "$str_def" ] || { echo "FAIL: cleanup() not found"; exit 1; }

# rm is shadowed to fail, standing in for the race with a background git writer.
for int_want in 0 7; do
    int_got=0
    bash -c 'set -euo pipefail
WORK_DIR=x SEEDED_CACHES=() SEEDED_FILES=()
rm() { return 1; }
'"$str_def"'
trap cleanup EXIT
exit '"$int_want" 2>/dev/null || int_got=$?
    check "failing rm keeps exit status $int_want" "$int_want" "$int_got"
done

# Real git: gc.auto must resolve to 0 under the harness's exported config.
str_exports="$(sed -n '/^export GIT_CONFIG_COUNT/,/^export GIT_CONFIG_KEY_1/p' "$SCRIPT")"
str_gc="$(bash -c "$str_exports"'; git config --get gc.auto' || true)"
check "gc.auto disabled for scaffold git" "0" "$str_gc"

[ "$int_failures" -eq 0 ]

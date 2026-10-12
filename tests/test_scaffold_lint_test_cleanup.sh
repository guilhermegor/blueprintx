#!/bin/bash

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

str_gc="$(bash -c 'source "$1"; git config --get gc.auto' _ "$REPO_ROOT/bin/lib/no_background_git.sh" || true)"
check "gc.auto disabled for scaffold git" "0" "$str_gc"
for str_script in scaffold_lint_test check_review_config_shipped; do
    int_got=0
    grep -q 'lib/no_background_git.sh' "$REPO_ROOT/bin/ci/$str_script.sh" || int_got=1
    check "$str_script.sh sources no_background_git.sh" "0" "$int_got"
done

[ "$int_failures" -eq 0 ]

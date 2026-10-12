#!/bin/bash
# Should-fail regression tests for bin/ci/check_lockfile_sync.sh (blueprintx#588).
# Both directions: a dependency missing from the lock must fail NAMING the package, a synced
# pair and a lockfile-less tier must pass.
#
# Usage: bash tests/test_check_lockfile_sync.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/bin/ci/check_lockfile_sync.sh"
path_tmp="$(mktemp -d)"
trap 'rm -rf "$path_tmp"' EXIT
int_failures=0

# $1 = description, $2 = package.json deps, $3 = lock root deps, $4 = lock node_modules keys
# (space separated, "-" for a tier without a lockfile), $5 = pass|fail, $6 = needle on fail.
run_case() {
    local path_root="$path_tmp/$RANDOM" str_got="pass" str_out
    mkdir -p "$path_root/templates/t"
    printf '{"name":"t","dependencies":%s}' "$2" >"$path_root/templates/t/package.json"
    if [ "$4" != "-" ]; then
        local str_mods="" str_k
        for str_k in $4; do str_mods="$str_mods,\"node_modules/$str_k\":{}"; done
        printf '{"packages":{"":{"dependencies":%s}%s}}' "$3" "$str_mods" \
            >"$path_root/templates/t/package-lock.json"
    fi
    str_out="$(bash "$GATE" --root "$path_root" 2>&1)" || str_got="fail"
    if [ "$str_got" != "$5" ] || { [ "$5" = fail ] && [[ "$str_out" != *"$6"* ]]; }; then
        echo "FAIL: $1 (got $str_got): $str_out"
        int_failures=$((int_failures + 1))
    else
        echo "ok: $1"
    fi
}

run_case "synced pair passes" '{"a":"^1.0.0"}' '{"a":"^1.0.0"}' "a" pass
run_case "dependency absent from lock fails naming it" '{"a":"^1.0.0","b":"^2.0.0"}' \
    '{"a":"^1.0.0"}' "a" fail "'b'"
run_case "spec drift fails naming the package" '{"a":"^2.0.0"}' '{"a":"^1.0.0"}' "a" fail "'a'"
run_case "declared but unresolved fails" '{"a":"^1.0.0"}' '{"a":"^1.0.0"}' "x" fail "no resolved"
run_case "tier without lockfile is skipped" '{"a":"^1.0.0"}' '{}' "-" pass

[ "$int_failures" -eq 0 ] || exit 1
echo "all lockfile-sync cases passed"

#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/bin/ci/scaffold_ts_test.sh"
int_failures=0

for str_skeleton in ts-lib react-spa-webpack; do
    str_got="pass"
    str_out="$(SCAFFOLD_TS_SABOTAGE=1 bash "$SCRIPT" "$str_skeleton" 2>&1)" || str_got="fail"
    if [ "$str_got" = "fail" ] && [[ "$str_out" =~ Tests:[[:space:]]+1\ failed ]]; then
        echo "ok: $str_skeleton fails on a broken shipped jest test"
    else
        echo "FAIL: $str_skeleton (got $str_got) did not report the jest failure"
        int_failures=$((int_failures + 1))
    fi
done
exit "$int_failures"

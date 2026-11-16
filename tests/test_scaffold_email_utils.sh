#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

check() {
    if [ "$2" = "$3" ]; then echo "PASS: $1"; else echo "FAIL: $1 (want '$2', got '$3')"; int_failures=$((int_failures + 1)); fi
}

source "$REPO_ROOT/bin/lib/scaffold_email_utils.sh"

COMMON_TEMPLATE_ROOT="$REPO_ROOT/templates/python-common"
LIST_FILES=(
    src/utils/signatures.py
    tests/unit/test_signatures.py
    tests/unit/test_ms_office_outlook_gateway.py
    src/utils/ms_office/outlook_gateway.py
)

run_case() {
    local str_flag="$1" str_want="$2" proj="$WORK_DIR/$1" str_rel
    mkdir -p "$proj/src/utils/ms_office" "$proj/tests/unit"
    printf 'x = 1\n' >"$proj/src/utils/ms_office/outlook_gateway.py"
    INCLUDE_EMAIL="$str_flag" copy_email_only_utils "$proj"
    for str_rel in "${LIST_FILES[@]}"; do
        check "email=$str_flag: $str_rel present=$str_want" "$str_want" "$([ -f "$proj/$str_rel" ] && echo yes || echo no)"
    done
}

for str_script in "$REPO_ROOT"/bin/scaffold/python_*.sh; do
    if grep -q 'copy_email_only_utils "' "$str_script"; then
        check "$(basename "$str_script") sources the lib" yes \
            "$(grep -qF 'lib/scaffold_email_utils.sh"' "$str_script" && echo yes || echo no)"
    fi
done

run_case true yes
run_case false no

[ "$int_failures" -eq 0 ] || { echo "$int_failures failure(s)"; exit 1; }
echo "all passed"

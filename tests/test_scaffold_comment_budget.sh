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

source "$REPO_ROOT/bin/lib/common.sh"

gate() {
    python3 "$1/bin/check_comment_budget.py" --root "$1" --require-baseline
}

fixture() {
    local proj="$WORK_DIR/$1" str_ext="$2" str_marker="$3"
    mkdir -p "$proj/src"
    printf 'x = 1\n' >"$proj/src/existing.$str_ext"
    [ "$str_ext" = "sh" ] && printf '#!/usr/bin/env bash\nx=1\n' >"$proj/src/existing.sh"
    scaffold_comment_budget "$proj" >/dev/null 2>&1
    check "$1: helper writes the baseline" yes "$([ -f "$proj/comment_budget_baseline.txt" ] && echo yes)"
    check "$1: routing table shipped" yes "$([ -f "$proj/bin/comment_budget_routing.txt" ] && echo yes)"
    gate "$proj" >/dev/null 2>&1
    check "$1: untouched project passes" 0 "$?"
    printf '%s an ordinary explanation\n' "$str_marker" >>"$proj/src/existing.$str_ext"
    str_out="$(gate "$proj" 2>&1)"
    check "$1: one added comment fails the gate" 1 "$?"
    check "$1: failure routes the knowledge" yes "$(grep -q 'SECURITY.md' <<<"$str_out" && grep -q 'CONTRIBUTING.md' <<<"$str_out" && echo yes)"
    printf 'y = 2\n' >"$proj/src/new.$str_ext"
    sed -i '$d' "$proj/src/existing.$str_ext"
    gate "$proj" >/dev/null 2>&1
    check "$1: removing the comment passes again" 0 "$?"
    printf '%s fresh file comment\n' "$str_marker" >>"$proj/src/new.$str_ext"
    gate "$proj" >/dev/null 2>&1
    check "$1: a new file carries zero comments" 1 "$?"
}

fixture bash-sh sh '#'
fixture ts ts '//'
fixture tsx tsx '//'
fixture js js '//'
fixture mjs mjs '//'
fixture py py '#'

proj="$WORK_DIR/refresh"
mkdir -p "$proj/src" "$proj/.github"
printf 'x=1\n' >"$proj/src/a.sh"
printf '# only comment\n' >"$proj/.github/w.yml"
scaffold_comment_budget "$proj" >/dev/null 2>&1
rm -rf "$proj/.github"
gate "$proj" >/dev/null 2>&1
check "a file removed after the baseline makes it stale" 1 "$?"
scaffold_comment_budget_refresh "$proj" >/dev/null 2>&1
gate "$proj" >/dev/null 2>&1
check "the refresh before a scaffold commit re-bases it" 0 "$?"

git -C "$proj" init -q -b main
git -C "$proj" add -A
printf '# late comment\n' >"$proj/src/late.sh"
scaffold_comment_budget_refresh "$proj" >/dev/null 2>&1
gate "$proj" >/dev/null 2>&1
check "the refresh counts a file added after the first commit" 0 "$?"

for str_name in python_ddd_service python_ddd_service_orm python_api_service python_mvc_service \
    python_mvc_service_orm python_lib_minimal ts_lib ts_react_app bash_cli ventoy_usb etcher_chromeos; do
    check "$str_name calls the baseline helper" 1 "$(grep -c '^    scaffold_comment_budget "\$PROJECT_PATH"$' "$REPO_ROOT/bin/scaffold/$str_name.sh")"
done

for str_file in templates/python-common/.pre-commit-config.yaml templates/bash-cli/.pre-commit-config.yaml \
    templates/etcher-chromeos/.pre-commit-config.yaml templates/ts-common/.husky/pre-commit \
    templates/python-common/.github/workflows/tests.yaml templates/bash-cli/.github/workflows/ci.yml \
    templates/etcher-chromeos/.github/workflows/ci.yml templates/ts-common/.github/workflows/lint.yml; do
    check "$str_file requires the baseline" 1 "$(grep -c 'check_comment_budget.py.*--require-baseline' "$REPO_ROOT/$str_file")"
done

[ "$int_failures" -eq 0 ] || { echo "$int_failures failure(s)"; exit 1; }
echo "all passed"

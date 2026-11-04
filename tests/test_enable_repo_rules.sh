#!/bin/bash

set -uo pipefail
while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e GIT_)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/templates/python-common/bin/enable_repo_rules.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

cat >"$WORK_DIR/gh" <<'STUB'
#!/bin/bash
case "$1 $2" in
"auth status") exit 0 ;;
"repo view") echo "o/r"; exit 0 ;;
"pr list")
    [ "${STUB_PRLIST_FAIL:-}" = 1 ] && { echo "boom" >&2; exit 1; }
    echo "7 aaa111"; echo "8 bbb222"; echo "9 ccc333"; echo "10 ddd444"; exit 0 ;;
esac
case "$*" in
*"/rulesets"*) [ "${STUB_RULESET:-}" = present ] && echo 42 ;;
*"git/ref/pull/8/merge"*) echo mmm888 ;;
*"pull/9/"*) exit 1 ;;
*"tool_name=CodeQL&ref=refs/pull/7/head"*) echo aaa111 ;;
*"tool_name=CodeQL&ref=refs/pull/8/merge"*) echo mmm888 ;;
*"&ref=refs/pull/10/"*) echo ddd444 ;;
esac
exit 0
STUB
chmod +x "$WORK_DIR/gh"

run_mode() {
    PATH="$WORK_DIR:$PATH" STUB_RULESET="${2:-}" bash "$SCRIPT" "$1" 2>&1
    echo "rc=$?"
}

assert_has() {
    if grep -q -- "$2" <<<"$3"; then
        echo "ok: $1"
    else
        echo "FAIL ($1): $(tr '\n' '|' <<<"$3")"
        int_failures=$((int_failures + 1))
    fi
}

assert_lacks() {
    if grep -q -- "$2" <<<"$3"; then
        echo "FAIL ($1): $(tr '\n' '|' <<<"$3")"
        int_failures=$((int_failures + 1))
    else
        echo "ok: $1"
    fi
}

test_check_ruleset_flags_missing() {
    local str_out
    str_out="$(run_mode check_ruleset)"
    assert_has "check_ruleset flags an absent ruleset" "NOT present" "$str_out"
    assert_has "check_ruleset exits 1 when absent" "rc=1" "$str_out"
}

test_check_ruleset_passes_when_present() {
    assert_has "check_ruleset exits 0 when present" "rc=0" "$(run_mode check_ruleset present)"
}

test_check_ruleset_unresolved_repo_is_unknown() {
    local str_out
    str_out="$(PATH="$WORK_DIR:$PATH" GITHUB_REPOSITORY="" STUB_NO_REPO=1 bash -c '
        gh() { [ "$1 $2" = "repo view" ] && return 0; command gh "$@"; }
        export -f gh
        bash "$0" check_ruleset' "$SCRIPT" 2>&1)"
    assert_has "unresolved repo is reported UNKNOWN" "UNKNOWN" "$str_out"
}

test_stranded_names_pr_without_analysis() {
    local str_out
    str_out="$(run_mode stranded)"
    assert_has "stranded names the PR with no analysis" "stranded\|no CodeQL analysis on their head: #" "$str_out"
    assert_lacks "stranded leaves the head-analysed PR #7 out" "head:.*#7" "$str_out"
    assert_lacks "stranded leaves the merge-analysed PR #8 out" "head:.*#8" "$str_out"
}

test_stranded_lookup_failure_is_unknown_not_stranded() {
    local str_out
    str_out="$(run_mode stranded)"
    assert_has "failed lookup names #9 as UNKNOWN" "open PRs #9 (UNKNOWN" "$str_out"
    assert_lacks "failed lookup is not labelled stranded" "head:.*#9" "$str_out"
}

test_stranded_pr_list_failure_is_unknown() {
    assert_has "pr list failure is UNKNOWN, not none" "UNKNOWN, not none" "$(STUB_PRLIST_FAIL=1 run_mode stranded)"
}

test_check_ruleset_flags_missing
test_check_ruleset_passes_when_present
test_check_ruleset_unresolved_repo_is_unknown
test_stranded_names_pr_without_analysis
test_stranded_lookup_failure_is_unknown_not_stranded
test_stranded_pr_list_failure_is_unknown
exit "$int_failures"

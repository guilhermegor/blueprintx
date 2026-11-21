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
    mkdir -p "$WORK_DIR/norepo"
    str_out="$(cd "$WORK_DIR/norepo" && PATH="$WORK_DIR:$PATH" GITHUB_REPOSITORY="" STUB_NO_REPO=1 bash -c '
        gh() { [ "$1 $2" = "repo view" ] && return 0; command gh "$@"; }
        export -f gh
        bash "$0" check_ruleset' "$SCRIPT" 2>&1)"
    assert_has "unresolved repo is reported UNKNOWN" "UNKNOWN" "$str_out"
}

test_main_resolves_slug_from_origin_when_graphql_fails() {
    local str_out
    mkdir -p "$WORK_DIR/withremote" "$WORK_DIR/f"
    git -C "$WORK_DIR/withremote" init -q
    git -C "$WORK_DIR/withremote" remote add origin https://github.com/acme/widget.git
    sed 's#^"repo view") echo "o/r"; exit 0 ;;#"repo view") echo "graphql down" >\&2; exit 1 ;;#' "$WORK_DIR/gh" >"$WORK_DIR/f/gh"
    chmod +x "$WORK_DIR/f/gh"
    str_out="$(cd "$WORK_DIR/withremote" && PATH="$WORK_DIR/f:$PATH" bash "$SCRIPT" 2>&1)"
    assert_lacks "origin slug survives a GraphQL outage" "No GitHub remote resolved" "$str_out"
}

test_main_without_any_remote_says_no_remote() {
    local str_out
    mkdir -p "$WORK_DIR/noremote" "$WORK_DIR/f"
    git -C "$WORK_DIR/noremote" init -q
    str_out="$(cd "$WORK_DIR/noremote" && PATH="$WORK_DIR/f:$PATH" bash "$SCRIPT" 2>&1)"
    assert_has "no remote at all still says so" "No GitHub remote resolved" "$str_out"
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

mkdir -p "$WORK_DIR/v"
cat >"$WORK_DIR/v/gh" <<'STUB'
#!/bin/bash
[ "$1 $2" = "auth status" ] && exit 0
[ "$1 $2" = "repo view" ] && { echo "o/r"; exit 0; }
str_rule='{"type":"required_status_checks","ruleset_id":42,"parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"Review threads answered"}]}}'
case "$2" in
repos/o/r) str_json='{"default_branch":"main"}' ;;
repos/o/r/rulesets) str_json="[{\"id\":42,\"name\":\"pr-quality-gate\",\"enforcement\":\"$STUB_ENFORCEMENT\"}]" ;;
repos/o/r/rulesets/42) str_json="{\"rules\":[$str_rule]}" ;;
repos/o/r/rules/branches/main*)
	case "$STUB_APPLIES" in
	1) str_json="[$str_rule]" ;;
	2) [[ " $* " == *" --paginate "* ]] && str_json="[] [$str_rule]" || str_json='[]' ;;
	*) str_json='[]' ;;
	esac
	;;
*) echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
esac
str_jq=""
while [ $# -gt 0 ]; do [ "$1" = "--jq" ] && str_jq="$2"; shift; done
jq -r "${str_jq:-.}" <<<"$str_json"
STUB
chmod +x "$WORK_DIR/v/gh"

run_verify() {
    mkdir -p "$WORK_DIR/norepo"
    (cd "$WORK_DIR/norepo" && PATH="$WORK_DIR/v:$PATH" GITHUB_REPOSITORY=o/r STUB_ENFORCEMENT="$1" STUB_APPLIES="$2" bash "$SCRIPT" "$3" 2>&1)
    echo "rc=$?"
}

test_verify_refuses_a_disabled_ruleset() {
    assert_has "a disabled ruleset is not proof of strict" "rc=1" "$(run_verify disabled 1 verify)"
}

test_verify_refuses_a_ruleset_that_skips_the_default_branch() {
    assert_has "a ruleset not applying to main is not proof" "rc=1" "$(run_verify active 0 verify)"
}

test_verify_accepts_an_active_ruleset_on_the_default_branch() {
    assert_has "an active, applicable ruleset verifies" "rc=0" "$(run_verify active 1 verify)"
}

test_verify_reads_a_rule_on_a_later_page() {
    assert_has "a rule on page 2 still verifies" "rc=0" "$(run_verify active 2 verify)"
}

test_check_ruleset_flags_a_disabled_ruleset() {
    assert_has "a disabled ruleset is not present" "rc=1" "$(run_verify disabled 1 check_ruleset)"
}

test_verify_refuses_a_disabled_ruleset
test_verify_refuses_a_ruleset_that_skips_the_default_branch
test_verify_accepts_an_active_ruleset_on_the_default_branch
test_check_ruleset_flags_a_disabled_ruleset
test_check_ruleset_flags_missing
test_check_ruleset_passes_when_present
test_verify_reads_a_rule_on_a_later_page
test_check_ruleset_unresolved_repo_is_unknown
test_stranded_names_pr_without_analysis
test_stranded_lookup_failure_is_unknown_not_stranded
test_stranded_pr_list_failure_is_unknown
test_main_resolves_slug_from_origin_when_graphql_fails
test_main_without_any_remote_says_no_remote
exit "$int_failures"

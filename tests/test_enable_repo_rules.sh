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
"repo view") echo "o/r" ;;
"pr list") echo "7 aaa111"; echo "8 bbb222" ;;
esac
case "$*" in
*"/rulesets "* | *"/rulesets") [ "${STUB_RULESET:-}" = present ] && echo 42 ;;
*"refs/pull/7/head"*) echo 0 ;;
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

test_check_ruleset_flags_missing() {
    local str_out
    str_out="$(run_mode check_ruleset)"
    assert_has "check_ruleset flags an absent ruleset" "NOT present" "$str_out"
    assert_has "check_ruleset exits 1 when absent" "rc=1" "$str_out"
}

test_check_ruleset_passes_when_present() {
    assert_has "check_ruleset exits 0 when present" "rc=0" "$(run_mode check_ruleset present)"
}

test_stranded_names_pr_without_analysis() {
    local str_out
    str_out="$(run_mode stranded)"
    assert_has "stranded names the PR with no analysis" "#8" "$str_out"
    if grep -q '#7' <<<"$str_out"; then
        echo "FAIL (stranded listed analysed PR #7)"
        int_failures=$((int_failures + 1))
    else
        echo "ok: stranded leaves the analysed PR out"
    fi
}

test_check_ruleset_flags_missing
test_check_ruleset_passes_when_present
test_stranded_names_pr_without_analysis
exit "$int_failures"

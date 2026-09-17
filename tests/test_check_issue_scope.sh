#!/bin/bash
# Should-fail regression tests for bin/ci/check_issue_scope.py (blueprintx#314).
#
# The gate blocks a PR — it must never report a false PASS (a violation that slips through)
# and never report a false UNKNOWN-as-pass (an unreadable API silently treated as "no
# violation found"). Both directions are exercised here, not just the happy path.
#
# A fake `gh` binary is put first on PATH; it prints PR_JSON / ISSUE_JSON verbatim for
# `gh pr view` / `gh api`, or fails when GH_FAIL_ON names the subcommand — the script under
# test is otherwise fully env-driven (GITHUB_REPOSITORY, PR_NUMBER), so no sandbox checkout is
# needed.
#
# Usage: bash tests/test_check_issue_scope.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

make_fake_gh() {
    local str_bin_dir
    str_bin_dir="$(mktemp -d)"
    cat > "$str_bin_dir/gh" <<'FAKE_GH'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
    pr)
        if [ "${GH_FAIL_ON:-}" = "pr" ]; then
            echo "simulated pr view failure" >&2
            exit 1
        fi
        printf '%s' "$PR_JSON"
        ;;
    api)
        if [ "${GH_FAIL_ON:-}" = "api" ]; then
            echo "simulated issue view failure" >&2
            exit 1
        fi
        printf '%s' "$ISSUE_JSON"
        ;;
    *)
        echo "fake gh: unhandled subcommand $1" >&2
        exit 1
        ;;
esac
FAKE_GH
    chmod +x "$str_bin_dir/gh"
    printf '%s' "$str_bin_dir"
}

expect_gate() {
    # $1 = description, $2 = expected pass|fail, $3 = needle that must appear in the output.
    local str_desc="$1" str_want="$2" str_needle="$3" str_got="pass" str_out str_fake_bin
    str_fake_bin="$(make_fake_gh)"
    str_out="$(PATH="$str_fake_bin:$PATH" python3 "$REPO_ROOT/bin/ci/check_issue_scope.py" 2>&1)" \
        || str_got="fail"
    rm -rf "$str_fake_bin"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
        int_failures=$((int_failures + 1))
        return
    fi
    if ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
        print_status "error" "$str_desc -> $str_want, but never said '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

test_no_linked_issue_passes() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="1"
    export PR_JSON='{"files":[{"path":"docs/x.md"}],"closingIssuesReferences":[],"commits":[]}'
    export ISSUE_JSON='{}'
    unset GH_FAIL_ON || true
    expect_gate "PR closes no issue" "pass" "not applicable"
}

test_files_within_declared_surface_passes() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="2"
    export PR_JSON='{"files":[{"path":"docs/issue-scope.md"}],"closingIssuesReferences":[{"number":314}],"commits":[{"messageBody":""}]}'
    export ISSUE_JSON='{"body":"before\n```surface\ndocs/issue-scope.md\n```\nafter"}'
    unset GH_FAIL_ON || true
    expect_gate "changed file inside declared surface" "pass" "scope OK"
}

test_file_outside_surface_fails() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="3"
    export PR_JSON='{"files":[{"path":"docs/issue-scope.md"},{"path":"bin/ci/unrelated.py"}],"closingIssuesReferences":[{"number":314}],"commits":[{"messageBody":""}]}'
    export ISSUE_JSON='{"body":"```surface\ndocs/issue-scope.md\n```"}'
    unset GH_FAIL_ON || true
    expect_gate "changed file outside declared surface, no override" "fail" \
        "bin/ci/unrelated.py"
}

test_override_trailer_passes() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="4"
    export PR_JSON='{"files":[{"path":"docs/issue-scope.md"},{"path":"bin/ci/unrelated.py"}],"closingIssuesReferences":[{"number":314}],"commits":[{"messageBody":"surface-override: needed for the migration"}]}'
    export ISSUE_JSON='{"body":"```surface\ndocs/issue-scope.md\n```"}'
    unset GH_FAIL_ON || true
    expect_gate "violation with surface-override trailer" "pass" "OVERRIDDEN"
}

test_undeclared_surface_warns_not_blocks() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="5"
    export PR_JSON='{"files":[{"path":"anything.py"}],"closingIssuesReferences":[{"number":314}],"commits":[{"messageBody":""}]}'
    export ISSUE_JSON='{"body":"no surface block on this issue"}'
    unset GH_FAIL_ON || true
    expect_gate "linked issue has no declared surface" "pass" "UNDECLARED-SURFACE"
}

test_unreadable_api_fails_loudly() {
    export GITHUB_REPOSITORY="o/r" PR_NUMBER="6"
    export PR_JSON='{}'
    export ISSUE_JSON='{}'
    export GH_FAIL_ON="pr"
    expect_gate "gh pr view fails (API unreadable)" "fail" "UNKNOWN"
    unset GH_FAIL_ON
}

main() {
    test_no_linked_issue_passes
    test_files_within_declared_surface_passes
    test_file_outside_surface_fails
    test_override_trailer_passes
    test_undeclared_surface_warns_not_blocks
    test_unreadable_api_fails_loudly

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures check_issue_scope.py regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "check_issue_scope.py: not-applicable, scope OK, violation, override, undeclared, and UNKNOWN all verified"
}

main "$@"

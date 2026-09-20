#!/bin/bash
# Should-fail regression tests for bin/ci/check_pr_file_count.py (blueprintx#551).
#
# The gate blocks a PR — it must fail LOUDLY (naming the offending count, not just a
# non-zero exit, since "it exited non-zero" also describes a crash) above the ceiling,
# stay quiet at/under it, and no-op on the default branch. Each case builds a real
# throwaway git repo with a real merge-base, rather than mocking git, because the gate's
# only interface IS git.
#
# Usage: bash tests/test_check_pr_file_count.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_pr_file_count.py"

int_failures=0

# Builds a repo with `main` at the merge-base, checked out onto a `feature` branch with
# $1 new staged files — mirroring pre-commit's index-based view (git diff --cached).
#
# The empty commit after `checkout -b` is load-bearing, not decoration: the gate's own
# no-op guard is `merge-base(HEAD, main) == HEAD`, which is also true of a branch's
# still-uncommitted FIRST commit (HEAD has not moved yet at pre-commit time). Diverging
# HEAD first is what makes THIS commit — not the one after it — the one under test,
# matching what CI sees for a real single-commit PR (its one commit already has a
# parent distinct from itself).
make_repo_with_staged_files() {
    local int_file_count="$1" str_repo str_i
    str_repo="$(mktemp -d)"
    git -C "$str_repo" init --quiet --initial-branch=main
    git -C "$str_repo" config user.email "test@example.com"
    git -C "$str_repo" config user.name "Test"
    echo "seed" > "$str_repo/seed.txt"
    git -C "$str_repo" add seed.txt
    git -C "$str_repo" commit --quiet -m "seed"
    git -C "$str_repo" checkout --quiet -b feature
    git -C "$str_repo" commit --quiet --allow-empty -m "branch setup"
    for ((str_i = 0; str_i < int_file_count; str_i++)); do
        echo "content" > "$str_repo/file_$str_i.txt"
    done
    git -C "$str_repo" add -A
    printf '%s' "$str_repo"
}

expect_gate() {
    # $1 = description, $2 = expected pass|fail, $3 = needle that must appear in output.
    local str_desc="$1" str_want="$2" str_needle="$3" str_repo="$4" str_got="pass" str_out
    str_out="$(cd "$str_repo" && python3 "$GATE" 2>&1)" || str_got="fail"
    rm -rf "$str_repo"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
        print_status "error" "$str_desc -> $str_want, but never said '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

test_within_ceiling_passes() {
    expect_gate "5 files, well under the ceiling" "pass" "" "$(make_repo_with_staged_files 5)"
}

test_at_ceiling_passes() {
    expect_gate "exactly 90 files, at the ceiling" "pass" "" "$(make_repo_with_staged_files 90)"
}

test_over_ceiling_fails_naming_the_count() {
    # The calibrated case: 91 files must fail AND the message must name "91", not just
    # exit non-zero — a crash also exits non-zero and would pass a weaker assertion.
    expect_gate "91 files, one over the ceiling" "fail" "91 files" \
        "$(make_repo_with_staged_files 91)"
}

test_default_branch_is_not_applicable() {
    # On main itself (merge-base == HEAD) the gate is a no-op regardless of file count —
    # there is no branch to compare against.
    local str_repo
    str_repo="$(mktemp -d)"
    git -C "$str_repo" init --quiet --initial-branch=main
    git -C "$str_repo" config user.email "test@example.com"
    git -C "$str_repo" config user.name "Test"
    echo "seed" > "$str_repo/seed.txt"
    git -C "$str_repo" add seed.txt
    git -C "$str_repo" commit --quiet -m "seed"
    expect_gate "on the default branch itself" "pass" "" "$str_repo"
}

main() {
    test_within_ceiling_passes
    test_at_ceiling_passes
    test_over_ceiling_fails_naming_the_count
    test_default_branch_is_not_applicable

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures check_pr_file_count.py regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "check_pr_file_count.py: within-ceiling, at-ceiling, over-ceiling (message verified), and default-branch no-op all confirmed"
}

main "$@"

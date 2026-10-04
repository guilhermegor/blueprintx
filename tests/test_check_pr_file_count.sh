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
# $2 ("diverged", the default, or "pre-first-commit") selects WHEN in the branch's life
# the commit under test happens. Both states are real and they used to behave
# differently: with an empty commit after `checkout -b`, HEAD has moved off the
# merge-base, which is what CI sees for a single-commit PR; without one, HEAD still
# points AT the branch point, which is what pre-commit sees for a branch's very first
# commit. The gate originally no-op'd on `merge-base(HEAD, main) == HEAD` and therefore
# waved the second state straight through (blueprintx#560).
make_repo_with_staged_files() {
    local int_file_count="$1" str_stage="${2:-diverged}" str_repo str_i
    str_repo="$(mktemp -d)"
    git -C "$str_repo" init --quiet --initial-branch=main
    git -C "$str_repo" config user.email "test@example.com"
    git -C "$str_repo" config user.name "Test"
    echo "seed" > "$str_repo/seed.txt"
    git -C "$str_repo" add seed.txt
    git -C "$str_repo" commit --quiet -m "seed"
    git -C "$str_repo" checkout --quiet -b feature
    if [ "$str_stage" = "diverged" ]; then
        git -C "$str_repo" commit --quiet --allow-empty -m "branch setup"
    fi
    for ((str_i = 0; str_i < int_file_count; str_i++)); do
        echo "content" > "$str_repo/file_$str_i.txt"
    done
    git -C "$str_repo" add -A
    printf '%s' "$str_repo"
}

# Builds a repo where `feature` carries $1 own committed files, `main` then gains $2 new
# files, and a merge of main into feature is left IN PROGRESS (--no-commit) — the state
# pre-commit sees on a "merge main into my branch" commit. The index then holds main's
# files too, which a base resolved from the pre-merge HEAD would charge to the branch.
make_repo_mid_merge() {
    local int_own="$1" int_incoming="$2" str_repo str_i
    str_repo="$(mktemp -d)"
    git -C "$str_repo" init --quiet --initial-branch=main
    git -C "$str_repo" config user.email "test@example.com"
    git -C "$str_repo" config user.name "Test"
    echo "seed" > "$str_repo/seed.txt"
    git -C "$str_repo" add seed.txt
    git -C "$str_repo" commit --quiet -m "seed"
    git -C "$str_repo" checkout --quiet -b feature
    for ((str_i = 0; str_i < int_own; str_i++)); do
        echo "own" > "$str_repo/own_$str_i.txt"
    done
    git -C "$str_repo" add -A
    git -C "$str_repo" commit --quiet -m "feature work"
    git -C "$str_repo" checkout --quiet main
    for ((str_i = 0; str_i < int_incoming; str_i++)); do
        echo "incoming" > "$str_repo/incoming_$str_i.txt"
    done
    git -C "$str_repo" add -A
    git -C "$str_repo" commit --quiet -m "main moves on"
    git -C "$str_repo" checkout --quiet feature
    git -C "$str_repo" merge --quiet --no-commit --no-ff main
    printf '%s' "$str_repo"
}

# Same as make_repo_mid_merge, but an OCTOPUS merge of `side` then `main` is left in
# progress: $1 own files on feature, $2 incoming files on main, $3 files on `side`. MAIN is
# the LAST MERGE_HEAD line, so resolving only the first line leaves main's delta charged to
# the branch; side's files are genuinely new to the PR and stay counted.
make_repo_octopus_mid_merge() {
    local int_own="$1" int_main="$2" int_side="$3" str_repo str_i
    str_repo="$(mktemp -d)"
    git -C "$str_repo" init --quiet --initial-branch=main
    git -C "$str_repo" config user.email "test@example.com"
    git -C "$str_repo" config user.name "Test"
    echo "seed" > "$str_repo/seed.txt"
    git -C "$str_repo" add seed.txt
    git -C "$str_repo" commit --quiet -m "seed"
    git -C "$str_repo" branch side
    git -C "$str_repo" checkout --quiet -b feature
    for ((str_i = 0; str_i < int_own; str_i++)); do
        echo "own" > "$str_repo/own_$str_i.txt"
    done
    git -C "$str_repo" add -A
    git -C "$str_repo" commit --quiet -m "feature work"
    git -C "$str_repo" checkout --quiet main
    for ((str_i = 0; str_i < int_main; str_i++)); do
        echo "main" > "$str_repo/main_$str_i.txt"
    done
    git -C "$str_repo" add -A
    git -C "$str_repo" commit --quiet -m "main moves on"
    git -C "$str_repo" checkout --quiet side
    for ((str_i = 0; str_i < int_side; str_i++)); do
        echo "side" > "$str_repo/side_$str_i.txt"
    done
    git -C "$str_repo" add -A
    git -C "$str_repo" commit --quiet -m "side moves on"
    git -C "$str_repo" checkout --quiet feature
    git -C "$str_repo" merge --quiet --no-commit --no-ff side main >/dev/null 2>&1
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

test_new_branch_before_first_commit_fails() {
    # The bypass blueprintx#560's review found: on a branch with no commit of its own,
    # merge-base(HEAD, main) == HEAD, so a merge-base-based no-op exits 0 with the whole
    # change staged. Same 91 files as the case above, same message expected.
    expect_gate "91 files staged on a branch with no commit yet" "fail" "91 files" \
        "$(make_repo_with_staged_files 91 pre-first-commit)"
}

test_merge_in_progress_ignores_incoming_delta() {
    # 10 own files + 100 incoming from main: the index holds 110 mid-merge, but the
    # branch's real cumulative diff is 10. Charging main's delta here rejected every
    # "merge main into my branch" commit on a PR of any size (186 reported vs 69 real).
    expect_gate "mid-merge, 10 own files, 100 incoming from main" "pass" "" \
        "$(make_repo_mid_merge 10 100)"
}

test_merge_in_progress_still_fails_real_oversize() {
    # The fix must not blind the gate: 91 own files stay a violation mid-merge.
    expect_gate "mid-merge, 91 own files" "fail" "91 files" "$(make_repo_mid_merge 91 5)"
}

test_octopus_merge_in_progress_ignores_every_incoming_head() {
    # 10 own files, 5 on `side`, 100 incoming from main (the second head): only the first
    # MERGE_HEAD line used to be excluded, so main's 100 files were charged to the branch.
    expect_gate "octopus mid-merge, main's 100 files on the second head" "pass" "" \
        "$(make_repo_octopus_mid_merge 10 100 5)"
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
    test_new_branch_before_first_commit_fails
    test_merge_in_progress_ignores_incoming_delta
    test_merge_in_progress_still_fails_real_oversize
    test_octopus_merge_in_progress_ignores_every_incoming_head
    test_default_branch_is_not_applicable

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures check_pr_file_count.py regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "check_pr_file_count.py: within-ceiling, at-ceiling, over-ceiling (message verified), pre-first-commit branch, merge-in-progress (both ways), and default-branch no-op all confirmed"
}

main "$@"

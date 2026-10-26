#!/bin/bash

set -euo pipefail

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_pr_file_count.py"

int_failures=0

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
    expect_gate "91 files, one over the ceiling" "fail" "91 files" \
        "$(make_repo_with_staged_files 91)"
}

test_new_branch_before_first_commit_fails() {
    expect_gate "91 files staged on a branch with no commit yet" "fail" "91 files" \
        "$(make_repo_with_staged_files 91 pre-first-commit)"
}

test_merge_in_progress_ignores_incoming_delta() {
    expect_gate "mid-merge, 10 own files, 100 incoming from main" "pass" "" \
        "$(make_repo_mid_merge 10 100)"
}

test_merge_in_progress_still_fails_real_oversize() {
    expect_gate "mid-merge, 91 own files" "fail" "91 files" "$(make_repo_mid_merge 91 5)"
}

test_octopus_merge_in_progress_ignores_every_incoming_head() {
    expect_gate "octopus mid-merge, main's 100 files on the second head" "pass" "" \
        "$(make_repo_octopus_mid_merge 10 100 5)"
}

test_default_branch_is_not_applicable() {
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

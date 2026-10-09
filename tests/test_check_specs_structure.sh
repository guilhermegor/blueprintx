#!/bin/bash
# Should-fail regression tests for bin/ci/check_specs_structure.sh (blueprintx#447, #583).
#
# The dangerous direction is a FALSE PASS, so every refusal is asserted by the diagnostic that
# names the cause, not by a bare non-zero exit (a crash exits non-zero too), and every rule has
# a control case that passes: without it a gate that rejects everything would satisfy the suite.
# Each case runs the real script against an isolated fixture tree through `--root`.
#
# Usage: bash tests/test_check_specs_structure.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

GATE="$REPO_ROOT/bin/ci/check_specs_structure.sh"
int_failures=0

make_tree() {
    # Prints a fresh fake repo root holding a valid .specs/ (CLAUDE.md + features/).
    local str_root
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/.specs/features"
    printf '# specs\n' >"$str_root/.specs/CLAUDE.md"
    printf '%s' "$str_root"
}

expect() {
    # $1 = description, $2 = tree root (consumed), $3 = pass|fail, $4 = diagnostic a failure must say.
    local str_desc="$1" str_root="$2" str_want="$3" str_needle="${4:-}" str_got="pass" str_out
    str_out="$(bash "$GATE" --root "$str_root" 2>&1)" || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
        int_failures=$((int_failures + 1))
    elif [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF -- "$str_needle"; then
        print_status "error" "$str_desc -> failed, but never said '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

feature() {
    # feature <root> <name> [file...]: a features/<name>/ directory holding the named files.
    local str_root="$1" str_name="$2"
    shift 2
    mkdir -p "$str_root/.specs/features/$str_name"
    [ "$#" -eq 0 ] || (cd "$str_root/.specs/features/$str_name" && touch "$@")
}

test_valid_tree_passes() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "one-thing" design.md plan.md tasks.md pr.md pr-2-follow-up.md
    mkdir -p "$str_root/.specs/backlog" "$str_root/.specs/_lessons"
    touch "$str_root/.specs/backlog/wave-one_20260101_000000.md" "$str_root/.specs/_lessons/any file"
    expect "a fully valid tree" "$str_root" pass "layout is valid"
}

test_no_specs_dir_is_a_skip() {
    local str_root
    str_root="$(mktemp -d)"
    expect "no .specs/ at all" "$str_root" pass "nothing to check"
}

test_missing_root_fails() {
    local str_out str_got="pass"
    str_out="$(bash "$GATE" --root /nonexistent-specs-root 2>&1)" || str_got="fail"
    if [ "$str_got" != "fail" ] || ! printf '%s' "$str_out" | grep -qF -- "--root needs an existing directory"; then
        print_status "error" "--root <missing> -> $str_got: $str_out"
        int_failures=$((int_failures + 1))
    fi
}

test_missing_claude_md_fails() {
    local str_root
    str_root="$(make_tree)"
    rm "$str_root/.specs/CLAUDE.md"
    expect "CLAUDE.md missing" "$str_root" fail ".specs/CLAUDE.md is missing"
}

test_stray_top_level_entry_fails() {
    local str_root
    str_root="$(make_tree)"
    touch "$str_root/.specs/notes.md"
    expect "stray top-level file" "$str_root" fail "unexpected top-level entry .specs/notes.md"
}

test_type_folder_fails() {
    local str_type str_root
    for str_type in bugfix chore feat fix docs refactor test tests; do
        str_root="$(make_tree)"
        feature "$str_root" "$str_type" design.md
        expect "type-folder $str_type/" "$str_root" fail "features/$str_type is a change type"
    done
}

test_type_folder_holding_features_fails() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "bugfix/null-guard" design.md
    expect "bugfix/<name>/design.md" "$str_root" fail "features/bugfix"
}

test_name_that_merely_contains_a_type_passes() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "bugfix-triage" design.md
    expect "bugfix-triage is a feature, not a type" "$str_root" pass
}

test_feature_floor() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "only-a-body" pr.md
    expect "pr.md alone" "$str_root" fail "none of design.md, plan.md or tasks.md"
    str_root="$(make_tree)"
    feature "$str_root" "tracked-first" tasks.md
    expect "tasks.md alone" "$str_root" pass
}

test_malformed_pr_name_fails() {
    local str_name str_root
    for str_name in pr-draft.md pr-1.md pr-x-slug.md pr-1-Bad_Slug.md pr1.md pr_draft.md PR.md; do
        str_root="$(make_tree)"
        feature "$str_root" "one-thing" design.md "$str_name"
        expect "malformed pr file $str_name" "$str_root" fail "is not pr.md or"
    done
}

test_non_directory_feature_entry_fails() {
    local str_root
    str_root="$(make_tree)"
    touch "$str_root/.specs/features/loose.md"
    expect "file directly under features/" "$str_root" fail "features/loose.md is not a directory"
}

test_gitkeep_in_features_is_tolerated() {
    local str_root
    str_root="$(make_tree)"
    touch "$str_root/.specs/features/.gitkeep"
    expect ".gitkeep keeping an empty features/" "$str_root" pass
}

test_bad_task_markers_fail() {
    local str_line str_root
    for str_line in '- [?] unknown' '- [X] upper' '- [] empty' '- [~]' '- [~] ' '* [done] word' \
        '+ [?] plus' '1. [?] ordered' '2) [?] paren' '- [~]	' '- [~] 	'; do
        str_root="$(make_tree)"
        feature "$str_root" "one-thing" design.md
        printf '%s\n' "$str_line" >"$str_root/.specs/features/one-thing/tasks.md"
        expect "task line '$str_line'" "$str_root" fail "markers are [ ], [~] <branch> and [x]"
    done
}

test_good_task_markers_pass() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "one-thing"
    printf '%s\n' '# Tasks' '- [ ] todo' '- [~] feat/branch-name doing' '- [x] done' \
        'prose with [brackets] is not a task' '```' '- [?] inside a fence is documentation' '```' \
        >"$str_root/.specs/features/one-thing/tasks.md"
    expect "legal markers, prose and a fenced example" "$str_root" pass
}

test_fence_tracking() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "one-thing"
    printf '%s\n' '~~~' '- [?] tilde-fenced example' '~~~' '````' '```' '- [?] nested' '````' \
        >"$str_root/.specs/features/one-thing/tasks.md"
    expect "tilde fence and a longer backtick fence" "$str_root" pass
    str_root="$(make_tree)"
    feature "$str_root" "one-thing"
    printf '%s\n' '```' '- [ ] opened and never closed' >"$str_root/.specs/features/one-thing/tasks.md"
    expect "unclosed fence" "$str_root" fail "unclosed code fence"
    str_root="$(make_tree)"
    feature "$str_root" "one-thing"
    printf '%s\n' '```' '~~~' '- [?] still inside the backtick fence' '```' \
        >"$str_root/.specs/features/one-thing/tasks.md"
    expect "other-character fence does not close" "$str_root" pass
}

test_pr_directory_is_not_a_body() {
    local str_root
    str_root="$(make_tree)"
    feature "$str_root" "one-thing" design.md
    mkdir "$str_root/.specs/features/one-thing/pr-1-x.md"
    expect "directory named like a PR body" "$str_root" fail "is not a file"
}

test_backlog_rules() {
    local str_root
    str_root="$(make_tree)"
    mkdir -p "$str_root/.specs/backlog"
    touch "$str_root/.specs/backlog/Bad_Name.md"
    expect "backlog file with a bad name" "$str_root" fail "does not match"
    str_root="$(make_tree)"
    mkdir -p "$str_root/.specs/backlog/nested"
    expect "directory inside backlog/" "$str_root" fail "is not a file"
}

test_shipped_skeleton_passes() {
    # The tree every scaffold copies (blueprintx#446): the gate must accept what BlueprintX ships.
    local str_root
    str_root="$(mktemp -d)"
    cp -r "$REPO_ROOT/templates/common/.specs" "$str_root/.specs"
    expect "the scaffold's shipped .specs/" "$str_root" pass "layout is valid"
    str_root="$(mktemp -d)"
    cp -r "$REPO_ROOT/templates/common/.specs" "$str_root/.specs"
    touch "$str_root/.specs/spec.md"
    expect "the retired top-level spec.md" "$str_root" fail "unexpected top-level entry .specs/spec.md"
}

run_default_root() {
    # Runs the project-layout copy of the gate with no --root, from an unrelated cwd, so a
    # cwd-derived default would pass where a script-location-derived one fails.
    (cd / && bash "$1/bin/check_specs_structure.sh" 2>&1)
}

test_default_root_follows_the_script_location() {
    local str_root str_out str_got="pass"
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/bin" "$str_root/.specs/features"
    printf '# specs\n' >"$str_root/.specs/CLAUDE.md"
    cp "$GATE" "$str_root/bin/check_specs_structure.sh"
    str_out="$(run_default_root "$str_root")" || str_got="fail"
    if [ "$str_got" != "pass" ]; then
        print_status "error" "default root, valid project tree -> $str_got: $str_out"
        int_failures=$((int_failures + 1))
    fi
    touch "$str_root/.specs/notes.md"
    str_got="pass"
    str_out="$(run_default_root "$str_root")" || str_got="fail"
    if [ "$str_got" != "fail" ] || ! printf '%s' "$str_out" | grep -qF -- "unexpected top-level entry .specs/notes.md"; then
        print_status "error" "default root, stray note -> $str_got: $str_out"
        int_failures=$((int_failures + 1))
    fi
    rm -rf "$str_root"
}

main() {
    test_shipped_skeleton_passes
    test_default_root_follows_the_script_location
    test_valid_tree_passes
    test_no_specs_dir_is_a_skip
    test_missing_root_fails
    test_missing_claude_md_fails
    test_stray_top_level_entry_fails
    test_type_folder_fails
    test_type_folder_holding_features_fails
    test_name_that_merely_contains_a_type_passes
    test_feature_floor
    test_malformed_pr_name_fails
    test_non_directory_feature_entry_fails
    test_gitkeep_in_features_is_tolerated
    test_bad_task_markers_fail
    test_good_task_markers_pass
    test_fence_tracking
    test_pr_directory_is_not_a_body
    test_backlog_rules
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures failure(s)"
        exit 1
    fi
    print_status "success" "all specs-structure checks passed"
}

main "$@"

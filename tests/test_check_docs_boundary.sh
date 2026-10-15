#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

make_sandbox() {
    local str_root
    str_root="$(mktemp -d ${1:+-p "$1"})"
    mkdir -p "$str_root/bin/ci"
    cp "$REPO_ROOT/bin/ci/check_docs_boundary.sh" "$str_root/bin/ci/check_docs_boundary.sh"
    printf '%s' "$str_root"
}

expect_gate() {
    local str_desc="$1" str_root="$2" str_want="$3" str_needle="${4:-}" str_got="pass" str_out
    str_out="$(bash "$str_root/bin/ci/check_docs_boundary.sh" 2>&1)" || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
        print_status "error" "$str_desc -> failed, but never said '$str_needle'"
        int_failures=$((int_failures + 1))
    fi
}

test_no_docs_dir_is_a_skip() {
    local str_root
    str_root="$(make_sandbox)"
    expect_gate "no docs/ directory" "$str_root" "pass" "nothing to check"
}

test_clean_docs_passes() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/guide"
    printf '# Hello\n' > "$str_root/docs/index.md"
    printf '# Guide\n' > "$str_root/docs/guide/usage.md"
    expect_gate "clean docs/ tree" "$str_root" "pass" "docs/ boundary is clean"
}

test_docs_backlog_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/backlog"
    printf '# Backlog\n' > "$str_root/docs/backlog/wave-1_20260101_000000.md"
    expect_gate "docs/backlog/ present" "$str_root" "fail" \
        "docs/backlog — working material"
}

test_lessons_file_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/guide"
    printf '# Lessons\n' > "$str_root/docs/guide/session-lessons.md"
    expect_gate "docs/**/*lessons* file" "$str_root" "fail" \
        "a lessons store"
}

test_superpowers_segment_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/.superpowers"
    printf 'notes\n' > "$str_root/docs/.superpowers/notes.md"
    expect_gate "docs/.superpowers/ segment" "$str_root" "fail" \
        "harness/tooling working material"
}

test_design_md_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/feature-x"
    printf '# Design\n' > "$str_root/docs/feature-x/design.md"
    expect_gate "stray docs/**/design.md" "$str_root" "fail" \
        "spec/plan artifact"
}

test_plan_md_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/feature-x"
    printf '# Plan\n' > "$str_root/docs/feature-x/plan.md"
    expect_gate "stray docs/**/plan.md" "$str_root" "fail" \
        "spec/plan artifact"
}

test_empty_docs_dir_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs"
    expect_gate "docs/ exists but is empty" "$str_root" "fail" \
        "contains nothing to check"
}

test_unreadable_docs_dir_fails() {
    if [ "$(id -u)" -eq 0 ]; then
        print_status "warning" "skipping unreadable-docs/ case: running as root"
        return
    fi
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs"
    chmod 000 "$str_root/docs"
    expect_gate "unreadable docs/ directory" "$str_root" "fail" "is not readable"
}

test_nested_security_md_fails() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/policies"
    printf '# Security Policy\n' > "$str_root/docs/policies/SECURITY.md"
    expect_gate "nested docs/**/SECURITY.md" "$str_root" "fail" \
        "root SECURITY.md"
}

test_every_rejection_names_a_destination() {
    local str_root str_out int_errors int_directed
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/backlog" "$str_root/docs/f" "$str_root/docs/.superpowers"
    printf 'x\n' > "$str_root/docs/backlog/note.md"
    printf 'x\n' > "$str_root/docs/my-lessons.md"
    printf 'x\n' > "$str_root/docs/f/plan.md"
    printf 'x\n' > "$str_root/docs/SECURITY.md"
    printf 'x\n' > "$str_root/docs/.superpowers/x.md"

    str_out="$(bash "$str_root/bin/ci/check_docs_boundary.sh" 2>&1)" || true
    rm -rf "$str_root"

    int_errors="$(printf '%s\n' "$str_out" | grep -c '^ERROR: docs/' || true)"
    int_directed="$(printf '%s\n' "$str_out" |
        grep -cE '^ERROR: docs/.*(belongs|move it|goes to|lessons\* stores|[.]specs/|CONTRIBUTING[.]md|README[.]md|SECURITY[.]md|own home)' || true)"

    if [ "$int_errors" -eq 0 ]; then
        print_status "error" "redirect contract -> expected rejections, got none"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ "$int_errors" -ne "$int_directed" ]; then
        print_status "error" \
            "redirect contract -> $int_errors rejection(s), only $int_directed named a destination"
        int_failures=$((int_failures + 1))
    fi
}

test_directory_symlink_loop_does_not_re_enter_the_tree() {
    local str_root str_out int_checked
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/a/b"
    printf '# ok\n' > "$str_root/docs/index.md"
    ln -s "$str_root/docs" "$str_root/docs/a/b/loop"

    str_out="$(timeout 20 bash "$str_root/bin/ci/check_docs_boundary.sh" 2>&1)" || true
    rm -rf "$str_root"

    int_checked="$(printf '%s' "$str_out" | sed -n 's/.*(\([0-9]*\) entries checked).*/\1/p')"
    if [ -z "$int_checked" ] || [ "$int_checked" -gt 10 ]; then
        print_status "error" \
            "symlink loop -> ${int_checked:-no} entries checked (a 3-file tree; >10 means it re-entered)"
        int_failures=$((int_failures + 1))
    fi
}

test_unreadable_nested_directory_fails_not_passes() {
    local str_root str_got="pass" str_out
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/secret/backlog"
    printf '# ok\n' > "$str_root/docs/index.md"
    printf 'x\n' > "$str_root/docs/secret/backlog/n.md"
    chmod 000 "$str_root/docs/secret"

    str_out="$(bash "$str_root/bin/ci/check_docs_boundary.sh" 2>&1)" || str_got="fail"
    chmod 755 "$str_root/docs/secret" 2>/dev/null || true
    rm -rf "$str_root"

    if [ "$str_got" != "fail" ]; then
        print_status "error" "unreadable nested dir -> passed (must fail: contents unchecked)"
        int_failures=$((int_failures + 1))
        return
    fi
    if ! printf '%s' "$str_out" | grep -qF "not readable/searchable"; then
        print_status "error" "unreadable nested dir -> failed, but never said why"
        int_failures=$((int_failures + 1))
    fi
}

test_templates_tree_is_deliberately_not_walked() {
    local str_root str_out str_got="pass" int_checked
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs" "$str_root/templates/ddd-service-native-db/docs/backlog"
    printf '# Hello\n' > "$str_root/docs/index.md"
    printf '# Ledger\n' \
        > "$str_root/templates/ddd-service-native-db/docs/backlog/wave_20260101_000000.md"
    printf '# Lessons\n' > "$str_root/templates/ddd-service-native-db/docs/my-lessons.md"

    str_out="$(bash "$str_root/bin/ci/check_docs_boundary.sh" 2>&1)" || str_got="fail"
    rm -rf "$str_root"

    if [ "$str_got" != "pass" ]; then
        print_status "error" "templates/ scope -> failed (the gate must not walk templates/)"
        int_failures=$((int_failures + 1))
        return
    fi
    if printf '%s' "$str_out" | grep -qF "templates"; then
        print_status "error" "templates/ scope -> passed, but the output named templates/"
        int_failures=$((int_failures + 1))
        return
    fi
    int_checked="$(printf '%s' "$str_out" | sed -n 's/.*(\([0-9]*\) entries checked).*/\1/p')"
    if [ "${int_checked:-0}" -ne 1 ]; then
        print_status "error" \
            "templates/ scope -> ${int_checked:-no} entries checked (docs/ holds exactly 1)"
        int_failures=$((int_failures + 1))
    fi
}

test_generated_project_root_flag_rejects_docs_backlog() {
    local str_proj str_gate str_got="pass"
    str_proj="$(mktemp -d)"
    mkdir -p "$str_proj/bin" "$str_proj/docs/backlog"
    cp "$REPO_ROOT/bin/ci/check_docs_boundary.sh" "$str_proj/bin/check_docs_boundary.sh"
    printf '# Hello\n' > "$str_proj/docs/index.md"
    printf '# Ledger\n' > "$str_proj/docs/backlog/x.md"
    str_gate="$str_proj/bin/check_docs_boundary.sh"
    bash "$str_gate" --root "$str_proj" > /dev/null 2>&1 && str_got="pass" || str_got="fail"
    if [ "$str_got" != "fail" ]; then
        print_status "error" "generated project docs/backlog/x.md -> passed (expected fail)"
        int_failures=$((int_failures + 1))
    fi
    rm -rf "$str_proj/docs/backlog"
    bash "$str_gate" --root "$str_proj" > /dev/null 2>&1 || {
        print_status "error" "generated project clean docs/ -> failed (expected pass)"
        int_failures=$((int_failures + 1))
    }
    bash "$str_gate" --root "$str_proj/missing" > /dev/null 2>&1 && {
        print_status "error" "bad --root -> passed (expected fail)"
        int_failures=$((int_failures + 1))
    }
    rm -rf "$str_proj"
}

make_git_sandbox() {
    local str_root
    str_root="$(make_sandbox)"
    git -C "$str_root" init -q
    printf 'docs/x-lessons.md\n' > "$str_root/.gitignore"
    mkdir -p "$str_root/docs"
    printf '# Hello\n' > "$str_root/docs/index.md"
    printf 'x\n' > "$str_root/docs/x-lessons.md"
    printf '%s' "$str_root"
}

test_git_ignored_lessons_file_passes() {
    expect_gate "git-ignored lessons file" "$(make_git_sandbox)" "pass" "docs/ boundary is clean"
}

test_unignored_lessons_file_still_fails() {
    local str_root
    str_root="$(make_git_sandbox)"
    : > "$str_root/.gitignore"
    expect_gate "untracked, non-ignored lessons file" "$str_root" "fail" "docs/x-lessons.md"
}

test_tracked_lessons_file_still_fails() {
    local str_root
    str_root="$(make_git_sandbox)"
    git -C "$str_root" add -f docs/x-lessons.md
    expect_gate "tracked lessons file" "$str_root" "fail" "docs/x-lessons.md"
}

test_git_ignored_directory_is_skipped_whole() {
    local str_root
    str_root="$(make_git_sandbox)"
    mkdir -p "$str_root/docs/backlog"
    printf 'x\n' > "$str_root/docs/backlog/todo.md"
    printf 'docs/backlog/\n' >> "$str_root/.gitignore"
    expect_gate "git-ignored directory" "$str_root" "pass" "docs/ boundary is clean"
}

test_tracked_file_under_ignored_directory_still_fails() {
    local str_root
    str_root="$(make_git_sandbox)"
    mkdir -p "$str_root/docs/backlog"
    printf 'x\n' > "$str_root/docs/backlog/todo.md"
    printf 'docs/backlog/\n' >> "$str_root/.gitignore"
    git -C "$str_root" add -f docs/backlog/todo.md
    expect_gate "tracked file under ignored directory" "$str_root" "fail" "docs/backlog"
}

test_enclosing_repo_ignore_does_not_leak_in() {
    local str_root str_outer
    str_outer="$(mktemp -d)"
    git -C "$str_outer" init -q
    printf '*\n' > "$str_outer/.gitignore"
    str_root="$(make_sandbox "$str_outer")"
    mkdir -p "$str_root/docs/backlog"
    printf 'x\n' > "$str_root/docs/backlog/todo.md"
    expect_gate "plain dir inside an ignoring repo" "$str_root" "fail" "docs/backlog"
    rm -rf "$str_outer"
}

test_inherited_git_dir_does_not_fake_an_own_repo() {
    local str_root str_other
    str_other="$(mktemp -d)"
    git -C "$str_other" init -q
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs/backlog"
    printf 'x\n' > "$str_root/docs/backlog/todo.md"
    printf 'docs/backlog/\n' > "$str_root/.gitignore"
    GIT_DIR="$str_other/.git" expect_gate "inherited GIT_DIR" "$str_root" "fail" "docs/backlog"
    rm -rf "$str_other"
}

test_global_excludes_do_not_hide_entries() {
    local str_root str_home
    str_home="$(mktemp -d)"
    printf '*-lessons.md\n' > "$str_home/ignore"
    printf '[core]\n\texcludesFile = %s/ignore\n' "$str_home" > "$str_home/gitconfig"
    str_root="$(make_git_sandbox)"
    : > "$str_root/.gitignore"
    GIT_CONFIG_GLOBAL="$str_home/gitconfig" expect_gate "global excludesFile" "$str_root" \
        "fail" "docs/x-lessons.md"
    rm -rf "$str_home"
}

test_all_ignored_docs_fails_closed() {
    local str_root
    str_root="$(make_git_sandbox)"
    printf 'docs/*\n' > "$str_root/.gitignore"
    expect_gate "docs/ with every entry ignored" "$str_root" "fail" "contains nothing to check"
}

main() {
    test_no_docs_dir_is_a_skip
    test_clean_docs_passes
    test_docs_backlog_fails
    test_lessons_file_fails
    test_superpowers_segment_fails
    test_design_md_fails
    test_nested_security_md_fails
    test_every_rejection_names_a_destination
    test_directory_symlink_loop_does_not_re_enter_the_tree
    test_unreadable_nested_directory_fails_not_passes
    test_plan_md_fails
    test_empty_docs_dir_fails
    test_unreadable_docs_dir_fails
    test_templates_tree_is_deliberately_not_walked
    test_generated_project_root_flag_rejects_docs_backlog
    test_git_ignored_lessons_file_passes
    test_unignored_lessons_file_still_fails
    test_tracked_lessons_file_still_fails
    test_git_ignored_directory_is_skipped_whole
    test_tracked_file_under_ignored_directory_still_fails
    test_enclosing_repo_ignore_does_not_leak_in
    test_inherited_git_dir_does_not_fake_an_own_repo
    test_global_excludes_do_not_hide_entries
    test_all_ignored_docs_fails_closed

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures check_docs_boundary.sh regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "check_docs_boundary.sh rejects docs/backlog/, *lessons* files, .superpowers segments, and stray design.md/plan.md"
}

main "$@"

#!/bin/bash
# Should-fail regression tests for bin/ci/check_docs_boundary.sh (blueprintx#536).
#
# The dangerous direction is a FALSE PASS: docs/backlog/, a *lessons* file, a
# .superpowers segment, or a stray design.md/plan.md under docs/ must never reach
# "docs/ boundary is clean." A control that only proves the happy path would have
# passed against the very defect this suite exists to catch (same shape as
# bin/ci/check_git_remote_guard.sh / tests/test_validate_meta.sh).
#
# check_docs_boundary.sh derives REPO_ROOT from its own script path (two dirs up), so
# each case runs it from an isolated sandbox root (its own bin/ci/check_docs_boundary.sh
# copy + docs/) rather than touching the real docs/ tree.
#
# Usage: bash tests/test_check_docs_boundary.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

make_sandbox() {
    # Prints the path of a fresh fake repo root: a copy of the real
    # check_docs_boundary.sh under bin/ci/, no docs/ yet — the caller populates it.
    local str_root
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/bin/ci"
    cp "$REPO_ROOT/bin/ci/check_docs_boundary.sh" "$str_root/bin/ci/check_docs_boundary.sh"
    printf '%s' "$str_root"
}

expect_gate() {
    # $1 = description, $2 = sandbox root (consumed + removed), $3 = expected pass|fail,
    # $4 = OPTIONAL diagnostic that must appear in the gate's output when $3 is "fail".
    #
    # ⚠️ $4 is what makes a failing case mean anything — a non-zero exit alone does not
    # prove the intended rule fired rather than some unrelated bug.
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
    # Control case: without it, every failing case below would pass even against a gate
    # that rejects everything.
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
    # A readable docs/ with zero entries is suspicious, not clean — never a silent pass.
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/docs"
    expect_gate "docs/ exists but is empty" "$str_root" "fail" \
        "contains nothing to check"
}

test_unreadable_docs_dir_fails() {
    # Skipped when running as root (e.g. some CI containers): chmod 000 does not block a
    # root reader, so the case would silently prove nothing rather than fail for real.
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
    # The rule is REDIRECT, not merely reject: "this does not belong here" without
    # "it belongs there" moves the problem to whoever reads the failure. This asserts the
    # CONTRACT across every rule at once, so a rule added later without a destination
    # fails here rather than shipping half-done.
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
    # docs/a/b/loop -> docs. Pre-fix the walk re-entered through the longer path and
    # reported "163 entries checked" on a 3-file tree, stopping only at the kernel's
    # ELOOP limit; a denied file inside the loop would also be reported many times.
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
    # docs/secret/ at mode 000, holding a REAL violation (docs/secret/backlog/). Pre-fix
    # the glob yielded nothing, walk recorded no error, and the gate printed
    # "boundary is clean" with rc=0 — success for having checked nothing.
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
    # blueprintx#576: the scope decision, asserted rather than left to the header comment.
    # The sandbox plants BOTH halves of the measured collision — a tier's shipped
    # docs/backlog/ (a product surface with its own gate) and a violation that WOULD be
    # rejected under the root tree — and requires the gate to pass, never naming templates/.
    # A later "just point it at templates/ too" therefore turns this case red instead of
    # silently condemning five shipped tiers.
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
    # One entry: docs/index.md. Anything more means the walk left docs/.
    int_checked="$(printf '%s' "$str_out" | sed -n 's/.*(\([0-9]*\) entries checked).*/\1/p')"
    if [ "${int_checked:-0}" -ne 1 ]; then
        print_status "error" \
            "templates/ scope -> ${int_checked:-no} entries checked (docs/ holds exactly 1)"
        int_failures=$((int_failures + 1))
    fi
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

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures check_docs_boundary.sh regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "check_docs_boundary.sh rejects docs/backlog/, *lessons* files, .superpowers segments, and stray design.md/plan.md"
}

main "$@"

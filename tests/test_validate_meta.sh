#!/bin/bash
# Should-fail regression tests for bin/ci/validate_meta.sh (blueprintx#407).
#
# validate_meta.sh runs in the `validate-meta` CI job, which blocks merge — and had zero
# tests. The dangerous direction is a FALSE PASS: a skeleton.meta with a missing key, an
# empty value, or a scaffold= path that does not exist must never reach
# "all skeleton.meta files are valid." A control that only proves the happy path would
# have passed against the very defect this suite exists to catch (same shape as
# bin/ci/check_git_remote_guard.sh).
#
# validate_meta.sh derives REPO_ROOT from its own script path (two dirs up), so each case
# runs it from an isolated sandbox root (its own bin/ci/validate_meta.sh copy + templates/)
# rather than touching the real templates/ tree.
#
# Usage: bash tests/test_validate_meta.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

REQUIRED_FIELDS=(language display_name description scaffold)
int_failures=0

base_value() {
    case "$1" in
        language) echo "python" ;;
        display_name) echo "Fake Skeleton" ;;
        description) echo "A fake skeleton for testing" ;;
        scaffold) echo "bin/scaffold/fake.sh" ;;
    esac
}

make_sandbox() {
    # Prints the path of a fresh fake repo root: a copy of the real validate_meta.sh under
    # bin/ci/, plus an empty templates/ dir for the caller to drop a skeleton.meta into.
    local str_root
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/bin/ci" "$str_root/templates"
    cp "$REPO_ROOT/bin/ci/validate_meta.sh" "$str_root/bin/ci/validate_meta.sh"
    printf '%s' "$str_root"
}

write_meta() {
    # $1 = sandbox root, $2.. = "key=value" lines to write verbatim into one skeleton.meta.
    local str_root="$1"
    shift
    mkdir -p "$str_root/templates/fake-skeleton"
    printf '%s\n' "$@" > "$str_root/templates/fake-skeleton/skeleton.meta"
}

expect_gate() {
    # $1 = description, $2 = sandbox root (consumed + removed), $3 = expected pass|fail.
    local str_desc="$1" str_root="$2" str_want="$3" str_got="pass"
    bash "$str_root/bin/ci/validate_meta.sh" >/dev/null 2>&1 || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
    fi
}

test_valid_meta_passes() {
    # Control case: without it, the three failing cases below would pass even against a
    # gate that rejects everything.
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/bin/scaffold"
    : > "$str_root/bin/scaffold/fake.sh"
    write_meta "$str_root" \
        "language=$(base_value language)" \
        "display_name=$(base_value display_name)" \
        "description=$(base_value description)" \
        "scaffold=$(base_value scaffold)"
    expect_gate "a fully valid skeleton.meta" "$str_root" "pass"
}

test_missing_key() {
    local str_field str_other str_root
    for str_field in "${REQUIRED_FIELDS[@]}"; do
        local -a list_lines=()
        str_root="$(make_sandbox)"
        mkdir -p "$str_root/bin/scaffold"
        : > "$str_root/bin/scaffold/fake.sh"
        for str_other in "${REQUIRED_FIELDS[@]}"; do
            [ "$str_other" = "$str_field" ] && continue
            list_lines+=("$str_other=$(base_value "$str_other")")
        done
        write_meta "$str_root" "${list_lines[@]}"
        expect_gate "missing key '$str_field'" "$str_root" "fail"
    done
}

test_empty_value() {
    # ⚠️ Distinct from a missing key: the key line IS present, just with nothing after `=`.
    local str_field str_other str_root
    for str_field in "${REQUIRED_FIELDS[@]}"; do
        local -a list_lines=()
        str_root="$(make_sandbox)"
        mkdir -p "$str_root/bin/scaffold"
        : > "$str_root/bin/scaffold/fake.sh"
        for str_other in "${REQUIRED_FIELDS[@]}"; do
            if [ "$str_other" = "$str_field" ]; then
                list_lines+=("$str_other=")
            else
                list_lines+=("$str_other=$(base_value "$str_other")")
            fi
        done
        write_meta "$str_root" "${list_lines[@]}"
        expect_gate "empty value for key '$str_field'" "$str_root" "fail"
    done
}

test_missing_scaffold_path() {
    # scaffold= resolves, but nothing exists at that path — deliberately do NOT seed
    # bin/scaffold/ in this sandbox.
    local str_root
    str_root="$(make_sandbox)"
    write_meta "$str_root" \
        "language=$(base_value language)" \
        "display_name=$(base_value display_name)" \
        "description=$(base_value description)" \
        "scaffold=bin/scaffold/does-not-exist.sh"
    expect_gate "scaffold= path that does not exist" "$str_root" "fail"
}

main() {
    test_valid_meta_passes
    test_missing_key
    test_empty_value
    test_missing_scaffold_path

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures validate_meta.sh regression assertion(s) failed"
        exit 1
    fi
    print_status "success" "validate_meta.sh rejects missing keys, empty values, and dead scaffold paths"
}

main "$@"

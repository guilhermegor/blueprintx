#!/bin/bash

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
    local str_root
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/bin/ci" "$str_root/templates"
    cp "$REPO_ROOT/bin/ci/validate_meta.sh" "$str_root/bin/ci/validate_meta.sh"
    printf '# CLAUDE.md\n\nfake-skeleton is documented here.\n' > "$str_root/CLAUDE.md"
    printf '%s' "$str_root"
}

write_meta() {
    local str_root="$1"
    shift
    mkdir -p "$str_root/templates/fake-skeleton"
    printf '%s\n' "$@" > "$str_root/templates/fake-skeleton/skeleton.meta"
}

expect_gate() {
    local str_desc="$1" str_root="$2" str_want="$3" str_needle="${4:-}" str_got="pass" str_out
    str_out="$(bash "$str_root/bin/ci/validate_meta.sh" 2>&1)" || str_got="fail"
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

test_valid_meta_passes() {
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
        expect_gate "missing key '$str_field'" "$str_root" "fail" \
            "field '$str_field' is missing or empty"
    done
}

test_empty_value() {
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
        expect_gate "empty value for key '$str_field'" "$str_root" "fail" \
            "field '$str_field' is missing or empty"
    done
}

test_missing_scaffold_path() {
    local str_root
    str_root="$(make_sandbox)"
    write_meta "$str_root" \
        "language=$(base_value language)" \
        "display_name=$(base_value display_name)" \
        "description=$(base_value description)" \
        "scaffold=bin/scaffold/does-not-exist.sh"
    expect_gate "scaffold= path that does not exist" "$str_root" "fail" \
        "scaffold path does not exist"
}

test_skeleton_not_documented_in_claude_md() {
    local str_root
    str_root="$(make_sandbox)"
    mkdir -p "$str_root/bin/scaffold"
    : > "$str_root/bin/scaffold/fake.sh"
    write_meta "$str_root" \
        "language=$(base_value language)" \
        "display_name=$(base_value display_name)" \
        "description=$(base_value description)" \
        "scaffold=$(base_value scaffold)"
    printf '# CLAUDE.md\n\nNothing about this skeleton here.\n' > "$str_root/CLAUDE.md"
    expect_gate "skeleton undocumented in CLAUDE.md" "$str_root" "fail" \
        "skeleton 'fake-skeleton' is not mentioned in CLAUDE.md"
}

main() {
    test_valid_meta_passes
    test_missing_key
    test_empty_value
    test_missing_scaffold_path
    test_skeleton_not_documented_in_claude_md

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures validate_meta.sh regression assertion(s) failed"
        exit 1
    fi
    print_status "success" \
        "validate_meta.sh rejects missing keys, empty values, dead scaffold paths, and undocumented skeletons"
}

main "$@"

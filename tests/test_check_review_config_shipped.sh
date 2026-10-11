#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
int_failures=0

make_copy() {
    local str_root
    str_root="$(mktemp -d)"
    (cd "$REPO_ROOT" && git ls-files -co --exclude-standard -z | tar --null -T - -cf -) \
        | tar -xf - -C "$str_root"
    printf '%s' "$str_root"
}

expect_gate() {
    local str_desc="$1" str_root="$2" str_want="$3" str_needle="$4"
    shift 4
    local str_got="pass" str_out
    str_out="$(bash "$str_root/bin/ci/check_review_config_shipped.sh" "$@" 2>&1)" || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ]; then
        echo "FAIL: $str_desc -> $str_got (expected $str_want)" >&2
        int_failures=$((int_failures + 1))
    elif [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
        echo "FAIL: $str_desc -> failed, but never said '$str_needle'" >&2
        int_failures=$((int_failures + 1))
    else
        echo "ok: $str_desc"
    fi
}

drop_copy_line() {
    sed -i '/\.gitattributes/d' "$1/bin/scaffold/ts_lib.sh"
}

drop_manifest_file() {
    rm "$1/templates/common/.gitattributes"
}

add_unshipped_entry() {
    printf '.never-shipped\n' >>"$1/templates/common/review-config.manifest"
}

test_real_tree_passes_static() {
    expect_gate "real tree, static" "$(make_copy)" pass "" --static
}

test_real_tree_passes_generated() {
    expect_gate "real tree, generated (bash-cli)" "$(make_copy)" pass "" --generated --skeleton bash-cli
}

test_dropped_copy_line_fails_static() {
    local str_root
    str_root="$(make_copy)"
    drop_copy_line "$str_root"
    expect_gate "dropped cp line, static" "$str_root" fail "ts_lib.sh never copies" --static
}

test_dropped_copy_line_fails_generated() {
    local str_root
    str_root="$(make_copy)"
    drop_copy_line "$str_root"
    expect_gate "dropped cp line, generated" "$str_root" fail "generated project lacks" \
        --generated --skeleton ts-lib
}

test_dropped_manifest_file_fails_static() {
    local str_root
    str_root="$(make_copy)"
    drop_manifest_file "$str_root"
    expect_gate "dropped manifest file, static" "$str_root" fail "does not exist under" --static
}

test_dropped_manifest_file_fails_generated() {
    local str_root
    str_root="$(make_copy)"
    drop_manifest_file "$str_root"
    expect_gate "dropped manifest file, generated" "$str_root" fail "" \
        --generated --skeleton bash-cli
}

test_unshipped_entry_fails_both_modes() {
    local str_root
    str_root="$(make_copy)"
    add_unshipped_entry "$str_root"
    expect_gate "unshipped entry, static" "$str_root" fail ".never-shipped" --static
    str_root="$(make_copy)"
    add_unshipped_entry "$str_root"
    expect_gate "unshipped entry, generated" "$str_root" fail ".never-shipped" \
        --generated --skeleton bash-cli
}

test_real_tree_passes_static
test_real_tree_passes_generated
test_dropped_copy_line_fails_static
test_dropped_copy_line_fails_generated
test_dropped_manifest_file_fails_static
test_dropped_manifest_file_fails_generated
test_unshipped_entry_fails_both_modes

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed" >&2; exit 1; }
echo "OK: review-config guard is red when it should be, green otherwise."

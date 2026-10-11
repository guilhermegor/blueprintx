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
    sed '/\.gitattributes/d' "$1/bin/scaffold/ts_lib.sh" >"$1/bin/scaffold/ts_lib.sh.tmp" \
        && mv "$1/bin/scaffold/ts_lib.sh.tmp" "$1/bin/scaffold/ts_lib.sh"
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

test_project_missing_manifest_file_fails() {
    local str_root
    str_root="$(make_copy)"
    mkdir -p "$str_root/generated-project"
    expect_gate "project missing manifest file" "$str_root" fail "generated project lacks" \
        --project "$str_root/generated-project"
}

test_empty_manifest_fails() {
    local str_root
    str_root="$(make_copy)"
    : >"$str_root/templates/common/review-config.manifest"
    expect_gate "empty manifest" "$str_root" fail "lists no paths" --static
}

test_unknown_skeleton_fails() {
    expect_gate "unknown skeleton" "$(make_copy)" fail "no skeleton named" \
        --generated --skeleton no-such-skeleton
}

test_comment_mention_does_not_satisfy_static() {
    local str_root
    str_root="$(make_copy)"
    drop_copy_line "$str_root"
    printf '# .gitattributes\n' >>"$str_root/bin/scaffold/ts_lib.sh"
    expect_gate "comment mention, static" "$str_root" fail "ts_lib.sh never copies" --static
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
test_project_missing_manifest_file_fails
test_empty_manifest_fails
test_unknown_skeleton_fails
test_comment_mention_does_not_satisfy_static
test_unshipped_entry_fails_both_modes

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed" >&2; exit 1; }
echo "OK: review-config guard is red when it should be, green otherwise."

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

expect_ts_lib_flagged() {
    local str_desc="$1" str_want="$2" str_line="$3" str_root str_out str_got="clean"
    str_root="$(make_copy)"
    drop_copy_line "$str_root"
    printf '%b\n' "$str_line" >>"$str_root/bin/scaffold/ts_lib.sh"
    str_out="$(bash "$str_root/bin/ci/check_review_config_shipped.sh" --static 2>&1 || true)"
    rm -rf "$str_root"
    printf '%s' "$str_out" | grep -qF "ts_lib.sh never copies" && str_got="flagged"
    if [ "$str_got" != "$str_want" ]; then
        echo "FAIL: $str_desc -> $str_got (expected $str_want)" >&2
        int_failures=$((int_failures + 1))
    else
        echo "ok: $str_desc"
    fi
}

test_static_rejects_wrong_copies() {
    local str_dst='"$project_path/.gitattributes"'
    expect_ts_lib_flagged "wrong source root" flagged "cp \"\$COMMON_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "backup source" flagged "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes.bak\" $str_dst"
    expect_ts_lib_flagged "destination-only match" flagged "cp \"\$SHARED_TEMPLATE_ROOT/.editorconfig\" $str_dst"
    expect_ts_lib_flagged "commented-out copy" flagged "# cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "recursive copy of another root" flagged \
        'cp -r "$COMMON_TEMPLATE_ROOT/." "$project_path"'
    expect_ts_lib_flagged "recursive copy of the right root to an unrelated destination" flagged \
        'cp -r "$SHARED_TEMPLATE_ROOT/." "/tmp/elsewhere"'
    expect_ts_lib_flagged "recursive copy of the root to a non-project variable" flagged \
        'cp -r "$SHARED_TEMPLATE_ROOT/." "$TMPDIR"'
    expect_ts_lib_flagged "loop copy (documented limit)" flagged \
        'for f in .gitattributes; do cp "$SHARED_TEMPLATE_ROOT/$f" "$project_path/$f"; done'
}

test_manifest_comment_and_slash_ignored() {
    local str_root
    str_root="$(make_copy)"
    printf '# note\n.gitattributes/\n' >>"$str_root/templates/common/review-config.manifest"
    expect_gate "comment line and trailing slash in manifest" "$str_root" pass "" --static
}

test_static_accepts_real_copies() {
    local str_dst='"$project_path/.gitattributes"'
    expect_ts_lib_flagged "plain copy" clean "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "cp -a of the shared root" clean 'cp -a "$SHARED_TEMPLATE_ROOT/." "$project_path"'
    expect_ts_lib_flagged "cp --recursive of the shared root" clean \
        'cp --recursive "$SHARED_TEMPLATE_ROOT/." "$project_path/"'
    expect_ts_lib_flagged "cp -r of the shared root" clean 'cp -r "$SHARED_TEMPLATE_ROOT/." "$project_path"'
    expect_ts_lib_flagged "mid-line cp" clean "[ -n \"\$x\" ] && cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "multi-source copy" clean \
        "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" \"\$SHARED_TEMPLATE_ROOT/.editorconfig\" \"\$project_path/\""
    expect_ts_lib_flagged "mkdir -p and cp" clean \
        "mkdir -p \"\$project_path\" && cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "stderr redirect after the copy" clean \
        "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst 2>/dev/null"
    expect_ts_lib_flagged "trailing comment and spaced redirect" clean \
        "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst > /dev/null # keep"
    expect_ts_lib_flagged "braced variable in the destination" clean \
        'cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "${project_path}/.gitattributes"'
    expect_ts_lib_flagged "redirect without a leading space" clean \
        "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" \"\$project_path/.gitattributes\">/dev/null"
    expect_ts_lib_flagged "parameter expansion with a hash" clean \
        "cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" \"\$project_path/\${x##*/}\" ; cp \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" $str_dst"
    expect_ts_lib_flagged "separated flags -v -r" clean 'cp -v -r "$SHARED_TEMPLATE_ROOT/." "$project_path"'
    expect_ts_lib_flagged "trailing-slash directory destination" clean \
        'cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/"'
    expect_ts_lib_flagged "continuation lines" clean \
        "cp \\\\\\n    \"\$SHARED_TEMPLATE_ROOT/.gitattributes\" \\\\\\n    $str_dst"
}

test_static_sourced_helper_counts() {
    local str_root str_out
    str_root="$(make_copy)"
    drop_copy_line "$str_root"
    printf 'helper() {\n    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$1/.gitattributes"\n}\n' \
        >>"$str_root/bin/lib/scaffold_package_json.sh"
    str_out="$(bash "$str_root/bin/ci/check_review_config_shipped.sh" --static 2>&1 || true)"
    rm -rf "$str_root"
    if printf '%s' "$str_out" | grep -qF "ts_lib.sh never copies"; then
        echo "FAIL: copy in a sourced helper -> flagged (expected clean)" >&2
        int_failures=$((int_failures + 1))
    else
        echo "ok: copy in a sourced helper"
    fi
}

test_static_nested_path_needs_its_own_parent() {
    local str_root str_out
    str_root="$(make_copy)"
    mkdir -p "$str_root/templates/common/sub"
    : >"$str_root/templates/common/sub/x.txt"
    printf 'sub/x.txt\n' >>"$str_root/templates/common/review-config.manifest"
    printf 'cp -r "$SHARED_TEMPLATE_ROOT/sub" "$project_path/sub"\n' >>"$str_root/bin/scaffold/ts_lib.sh"
    printf 'cp -r "$COMMON_TEMPLATE_ROOT/.github" "$project_path/.github"\n' >>"$str_root/bin/scaffold/bash_cli.sh"
    str_out="$(bash "$str_root/bin/ci/check_review_config_shipped.sh" --static 2>&1 || true)"
    rm -rf "$str_root"
    if printf '%s' "$str_out" | grep -qF "ts_lib.sh never copies 'sub/x.txt'"; then
        echo "FAIL: cp -r of the right parent -> flagged (expected clean)" >&2
        int_failures=$((int_failures + 1))
    elif ! printf '%s' "$str_out" | grep -qF "bash_cli.sh never copies 'sub/x.txt'"; then
        echo "FAIL: cp -r of an unrelated parent -> not flagged" >&2
        int_failures=$((int_failures + 1))
    else
        echo "ok: nested path accepts only its own parent"
    fi
}

test_dropped_greptile_copy_fails_static() {
    local str_root
    str_root="$(make_copy)"
    sed -i '/&& cp .*\.greptile/d' "$str_root/bin/scaffold/bash_cli.sh"
    expect_gate "dropped .greptile copy, static" "$str_root" fail \
        "bash_cli.sh never copies '.greptile/config.json'" --static
}

test_bad_arguments_are_rejected() {
    expect_gate "unknown flag" "$(make_copy)" fail "usage:" --generated --skeletn bash-cli
    expect_gate "trailing argument" "$(make_copy)" fail "usage:" --static extra
    expect_gate "skeleton without a name" "$(make_copy)" fail "usage:" --generated --skeleton
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
test_unshipped_entry_fails_both_modes
test_static_rejects_wrong_copies
test_manifest_comment_and_slash_ignored
test_static_accepts_real_copies
test_static_sourced_helper_counts
test_static_nested_path_needs_its_own_parent
test_bad_arguments_are_rejected
test_dropped_greptile_copy_fails_static

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed" >&2; exit 1; }
echo "OK: review-config guard is red when it should be, green otherwise."

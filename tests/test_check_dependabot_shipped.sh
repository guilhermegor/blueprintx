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
    local str_got="pass" str_out
    str_out="$(bash "$str_root/bin/ci/check_dependabot_shipped.sh" --static 2>&1)" || str_got="fail"
    rm -rf "$str_root"
    if [ "$str_got" != "$str_want" ] || ! grep -qF -- "$str_needle" <<<"$str_out"; then
        echo "FAIL: $str_desc -> $str_got: $str_out" >&2
        int_failures=$((int_failures + 1))
    else
        echo "ok: $str_desc"
    fi
}

test_missing_assignees_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i '/assignees:/,+1d' "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "template without assignees" "$str_root" fail "needs the \${GITHUB_USERNAME} assignee"
}

test_dropped_substitution_fails() {
    local str_script str_root
    for str_script in ts_lib ts_react_app bash_cli python_lib_minimal; do
        str_root="$(make_copy)"
        sed -i -E 's#^(\s*)(GITHUB_USERNAME="[^"]*" )?envsubst .* < ("[^"]*dependabot\.yml") .*#\1cp \3 "\$project_path/.github/dependabot.yml"#' "$str_root/bin/scaffold/$str_script.sh"
        expect_gate "dropped substitution, $str_script" "$str_root" fail "$str_script.sh never copies"
    done
}

test_dropped_inline_prefix_fails() {
    local str_script str_root
    for str_script in ts_lib ts_react_app bash_cli; do
        str_root="$(make_copy)"
        sed -i -E 's#^(\s*)GITHUB_USERNAME="\$GITHUB_USERNAME" (envsubst .*dependabot\.yml)#\1\2#' \
            "$str_root/bin/scaffold/$str_script.sh"
        expect_gate "dropped inline prefix, $str_script" "$str_root" fail "$str_script.sh never copies"
    done
}

test_empty_assignee_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i -E 's#^(      - )"\$\{GITHUB_USERNAME\}"#\1""#' "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "empty assignee value" "$str_root" fail "needs the \${GITHUB_USERNAME} assignee"
}

test_hardcoded_assignee_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i -E 's#^(      - )"\$\{GITHUB_USERNAME\}"#\1"someone"#' "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "hard-coded assignee" "$str_root" fail "needs the \${GITHUB_USERNAME} assignee"
}

test_promote_unrendered_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i -E '0,/envsubst .*dependabot\.yml/s#envsubst [^<]*< ("[^"]*dependabot\.yml")#cp \1#' \
        "$str_root/bin/promote_offline_to_online.sh"
    expect_gate "promote copies dependabot.yml raw" "$str_root" fail "promote_offline_to_online.sh renders"
}

test_promote_dropped_inline_prefix_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i -E '0,/GITHUB_USERNAME="\$GITHUB_USERNAME" envsubst/s#GITHUB_USERNAME="\$GITHUB_USERNAME" (envsubst)#\1#' \
        "$str_root/bin/promote_offline_to_online.sh"
    expect_gate "promote dropped inline owner" "$str_root" fail "promote_offline_to_online.sh renders"
}

test_promote_deleted_render_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i '0,/envsubst .*dependabot\.yml/{/envsubst .*dependabot\.yml/d}' \
        "$str_root/bin/promote_offline_to_online.sh"
    expect_gate "promote render deleted" "$str_root" fail "expected 5"
}

test_promote_all_renders_deleted_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i '/envsubst .*dependabot\.yml/d' "$str_root/bin/promote_offline_to_online.sh"
    expect_gate "every promote render deleted" "$str_root" fail "renders dependabot.yml 0 time(s)"
}

test_second_assignee_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i -E 's#^(      - "\$\{GITHUB_USERNAME\}")#\1\n      - "someone"#' "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "second hard-coded assignee" "$str_root" fail "needs the \${GITHUB_USERNAME} assignee"
}

test_real_tree_passes() {
    expect_gate "real tree" "$(make_copy)" pass "OK:"
}

test_dropped_copy_line_fails() {
    local str_root
    for str_script in ts_lib ts_react_app bash_cli python_lib_minimal; do
        str_root="$(make_copy)"
        sed -i '/dependabot\.yml/d' "$str_root/bin/scaffold/$str_script.sh"
        expect_gate "dropped copy, $str_script" "$str_root" fail "$str_script.sh never copies"
    done
}

test_missing_cooldown_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i '/cooldown:/d' "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "template without cooldown" "$str_root" fail "exactly one cooldown"
}

test_partial_cooldown_fails() {
    local str_root
    str_root="$(make_copy)"
    awk '/^    cooldown:/ && !int_done { int_skip = 4; int_done = 1 } int_skip > 0 { int_skip--; next } 1' \
        "$str_root/templates/ts-common/dependabot.yml" >"$str_root/out.yml"
    mv "$str_root/out.yml" "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "npm block without cooldown" "$str_root" fail "exactly one cooldown"
}

test_unparseable_file_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i 's/^  - package-ecosystem:/    - package-ecosystem:/; /cooldown:/d' \
        "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "file with no recognizable blocks" "$str_root" fail "exactly one cooldown"
}

test_duplicate_cooldown_fails() {
    local str_root
    str_root="$(make_copy)"
    sed -i '0,/^    cooldown:/s//    cooldown:\n      default-days: 1\n    cooldown:/' \
        "$str_root/templates/ts-common/dependabot.yml"
    expect_gate "duplicate cooldown in one block" "$str_root" fail "exactly one cooldown"
}

test_missing_source_fails() {
    local str_root
    str_root="$(make_copy)"
    rm "$str_root/templates/common/.github/dependabot.yml"
    expect_gate "missing source file" "$str_root" fail "copies missing file"
}

test_real_tree_passes
test_missing_assignees_fails
test_dropped_substitution_fails
test_dropped_copy_line_fails
test_dropped_inline_prefix_fails
test_empty_assignee_fails
test_hardcoded_assignee_fails
test_promote_unrendered_fails
test_promote_dropped_inline_prefix_fails
test_promote_deleted_render_fails
test_promote_all_renders_deleted_fails
test_second_assignee_fails
test_missing_cooldown_fails
test_partial_cooldown_fails
test_unparseable_file_fails
test_duplicate_cooldown_fails
test_missing_source_fails

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed" >&2; exit 1; }
echo "OK: dependabot guard is red when it should be, green otherwise."

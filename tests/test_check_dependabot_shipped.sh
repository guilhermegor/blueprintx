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
test_dropped_copy_line_fails
test_missing_cooldown_fails
test_partial_cooldown_fails
test_unparseable_file_fails
test_duplicate_cooldown_fails
test_missing_source_fails

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed" >&2; exit 1; }
echo "OK: dependabot guard is red when it should be, green otherwise."

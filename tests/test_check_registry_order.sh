#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

GATE="$REPO_ROOT/templates/python-common/bin/check_registry_order.py"
INIT_TMPL="$REPO_ROOT/templates/lib-minimal/rendered/package__init__.py.tmpl"
int_failures=0

unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

make_repo() {
    local str_root
    str_root="$(mktemp -d)"
    mkdir -p "$str_root/src/pkg" "$str_root/docs"
    sed 's/${PROJECT_NAME}/pkg/' "$INIT_TMPL" > "$str_root/src/pkg/__init__.py"
    printf 'def main() -> None:\n    return None\n' > "$str_root/src/pkg/main.py"
    printf '# Pkg\n\nEvery function in the API reference.\n' > "$str_root/README.md"
    git -C "$str_root" init -q -b main
    git -C "$str_root" add -A
    git -C "$str_root" commit -q -m base
    printf '%s' "$str_root"
}

add_module() {
    local str_root="$1" str_mod="$2" str_prev="$3"
    printf 'def %s() -> None:\n    return None\n' "$str_mod" > "$str_root/src/pkg/$str_mod.py"
    if [ "$str_prev" = "main" ]; then
        sed -i "s/^from .main import main/from .main import main\nfrom .$str_mod import $str_mod/" "$str_root/src/pkg/__init__.py"
    else
        sed -i "s/^from .main import main/from .$str_mod import $str_mod\nfrom .main import main/" "$str_root/src/pkg/__init__.py"
    fi
    sed -i "s/^    \"$str_prev\",/    \"$str_prev\",\n    \"$str_mod\",/" "$str_root/src/pkg/__init__.py"
    git -C "$str_root" add -A
    git -C "$str_root" commit -q -m "add $str_mod"
}

run_gate() {
    (cd "$1" && python3 "$GATE" 2>&1)
}

expect() {
    local str_desc="$1" str_want="$2" str_root="$3" str_needle="${4:-}" str_got="pass" str_out
    str_out="$(run_gate "$str_root")" || str_got="fail"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
    elif [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
        print_status "error" "$str_desc -> never said '$str_needle'"
        int_failures=$((int_failures + 1))
    fi
    rm -rf "$str_root"
}

test_two_branches_merge_clean_and_pass() {
    local str_root str_got="clean" str_name
    str_root="$(make_repo)"
    git -C "$str_root" checkout -q -b a
    add_module "$str_root" alpha __version__
    git -C "$str_root" checkout -q main
    git -C "$str_root" checkout -q -b b
    add_module "$str_root" zeta main
    git -C "$str_root" merge -q a -m merge >/dev/null 2>&1 || str_got="conflict"
    if [ "$str_got" != "clean" ]; then
        print_status "error" "two module branches conflicted"
        int_failures=$((int_failures + 1))
        rm -rf "$str_root"
        return
    fi
    for str_name in alpha zeta; do
        if ! grep -q "^from .$str_name import $str_name\$" "$str_root/src/pkg/__init__.py" \
            || ! grep -q "^    \"$str_name\",\$" "$str_root/src/pkg/__init__.py"; then
            print_status "error" "merge lost the import or the __all__ entry of $str_name"
            int_failures=$((int_failures + 1))
        fi
    done
    expect "merged registry passes the gate" pass "$str_root" "no stored counts"
}

test_template_init_passes() {
    expect "fresh template" pass "$(make_repo)"
}

test_unsorted_all_fails() {
    local str_root
    str_root="$(make_repo)"
    python3 - "$str_root/src/pkg/__init__.py" <<'P'
import sys
p = sys.argv[1]
s = open(p).read().replace('    "__version__",\n    "main",\n', '    "main",\n    "__version__",\n')
open(p, "w").write(s)
P
    expect "unsorted __all__" fail "$str_root" "not sorted"
}

test_one_line_all_fails() {
    local str_root
    str_root="$(make_repo)"
    python3 - "$str_root/src/pkg/__init__.py" <<'P'
import sys
p = sys.argv[1]
s = open(p).read().replace('[\n    "__version__",\n    "main",\n]', '["__version__", "main"]')
open(p, "w").write(s)
P
    expect "one-line __all__" fail "$str_root" "one entry per line"
}

test_stored_count_fails() {
    local str_root
    str_root="$(make_repo)"
    printf 'Ships 18 modules.\n' >> "$str_root/README.md"
    expect "stored count" fail "$str_root" "stored count"
}

test_count_in_code_fence_passes() {
    local str_root
    str_root="$(make_repo)"
    printf '```\n18 modules\n```\n' >> "$str_root/README.md"
    expect "count inside a fence" pass "$str_root"
}

expect_init() {
    local str_desc="$1" str_body="$2" str_needle="$3" str_root
    str_root="$(make_repo)"
    printf '%b' "$str_body" > "$str_root/src/pkg/__init__.py"
    expect "$str_desc" fail "$str_root" "$str_needle"
}

test_unreadable_all_forms_fail() {
    local str_literal="must be one literal list"
    expect_init "dynamic __all__" '__all__ = ["a"] + ["b"]\n' "$str_literal"
    expect_init "augmented __all__" '__all__ = [\n    "a",\n]\n__all__ += ["b"]\n' "$str_literal"
    expect_init "starred entry" '__all__ = [\n    *other,\n]\n' "$str_literal"
    expect_init "tuple-unpacked __all__" '__all__, other = ["a"], 1\n' "$str_literal"
    expect_init "tuple-unpacked literal tuple" '__all__, other = (\n    "a",\n    "b",\n)\n' "$str_literal"
    expect_init "appended __all__" '__all__ = [\n    "a",\n]\n__all__.append("b")\n' "$str_literal"
    expect_init "extended __all__" '__all__ = [\n    "a",\n]\n__all__.extend(["b"])\n' "$str_literal"
    expect_init "non-string entry" '__all__ = [\n    1,\n]\n' "$str_literal"
}

test_annotated_and_nested_all_are_checked() {
    expect_init "annotated __all__" '__all__: list[str] = [\n    "b",\n    "a",\n]\n' "not sorted"
    expect_init "case-only tie" '__all__ = [\n    "foo",\n    "Foo",\n]\n' "not sorted"
    expect_init "nested __all__" 'if True:\n    __all__ = [\n        "b",\n        "a",\n    ]\n' "not sorted"
}

test_entry_sharing_a_bracket_line_fails() {
    local str_layout="one entry per line"
    expect_init "single entry on the bracket line" '__all__ = ["one"]\n' "$str_layout"
    expect_init "entry on the opening bracket" '__all__ = ["a",\n    "b",\n]\n' "$str_layout"
    expect_init "entry on the closing bracket" '__all__ = [\n    "a",\n    "b"]\n' "$str_layout"
}

test_no_all_anywhere_fails() {
    local str_root
    str_root="$(make_repo)"
    printf '"""pkg."""\n' > "$str_root/src/pkg/__init__.py"
    expect "zero __all__ lists" fail "$str_root" "ZERO"
}

main() {
    local str_fn
    for str_fn in $(declare -F | awk '$3 ~ /^test_/ {print $3}'); do
        "$str_fn"
    done
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures check(s) failed"
        exit 1
    fi
    print_status "success" "registry order gate: all checks passed"
}

main "$@"

#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

GATE="$REPO_ROOT/templates/python-common/bin/check_template_residue.py"
PLACEHOLDER="$REPO_ROOT/templates/lib-minimal/main.py"
int_failures=0
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

make_project() {
    local str_root
    str_root="$(mktemp -d -p "$TMP_ROOT")"
    mkdir -p "$str_root/src/pkg/_internal/utils"
    printf '[tool.poetry.dependencies]\npython = ">=3.11"\nnumpy = ">=1"\npython-dateutil = "^2"\n' \
        > "$str_root/pyproject.toml"
    printf 'from .main import main\n' > "$str_root/src/pkg/__init__.py"
    printf 'from ._internal.utils.used import used\n\n\ndef main() -> None:\n    used()\n' \
        > "$str_root/src/pkg/main.py"
    : > "$str_root/src/pkg/_internal/__init__.py"
    : > "$str_root/src/pkg/_internal/utils/__init__.py"
    printf 'import dateutil\n\n\ndef used() -> None:\n    return None\n' \
        > "$str_root/src/pkg/_internal/utils/used.py"
    printf '%s' "$str_root"
}

use_placeholder() {
    mkdir -p "$1/src/pkg/_internal/utils/typing"
    printf 'def type_checker(fn):\n    return fn\n' > "$1/src/pkg/_internal/utils/typing/__init__.py"
    cp "$PLACEHOLDER" "$1/src/pkg/main.py"
}

add_unused_util() {
    printf 'import numpy\nimport dateutil\nimport json\n' > "$1/src/pkg/_internal/utils/unused.py"
}

expect() {
    local str_desc="$1" str_want="$2" str_root="$3" str_needle="$4"
    shift 4
    local str_got="pass" str_out
    str_out="$(python3 "$GATE" --root "$str_root" "$@" 2>&1)" || str_got="fail"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
        int_failures=$((int_failures + 1))
    elif [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF -- "$str_needle"; then
        print_status "error" "$str_desc -> never said '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

expect_absent() {
    local str_desc="$1" str_root="$2" str_needle="$3" str_out
    str_out="$(python3 "$GATE" --root "$str_root" 2>&1)" || true
    if printf '%s' "$str_out" | grep -qF -- "$str_needle"; then
        print_status "error" "$str_desc -> reported '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

test_clean_project_passes_strict() {
    local str_root
    str_root="$(make_project)"
    expect "every util reachable" pass "$str_root" "0 unreachable" --strict
    rm -rf "$str_root"
}

test_template_placeholder_fails() {
    local str_root
    str_root="$(make_project)"
    use_placeholder "$str_root"
    expect "template placeholder main.py" fail "$str_root" "placeholder"
    rm -rf "$str_root"
}

test_reformatted_placeholder_fails() {
    local str_root
    str_root="$(make_project)"
    use_placeholder "$str_root"
    sed "s/\"Hello from lib-minimal!\"/\"Hello from \" 'lib-minimal!'/" "$PLACEHOLDER" \
        > "$str_root/src/pkg/main.py"
    if grep -qF 'Hello from lib-minimal!' "$str_root/src/pkg/main.py"; then
        print_status "error" "reformat fixture still holds the contiguous literal"
        int_failures=$((int_failures + 1))
    fi
    expect "split, requoted placeholder main.py" fail "$str_root" "placeholder"
    rm -rf "$str_root"
}

test_placeholder_does_not_root_the_walk() {
    local str_root
    str_root="$(make_project)"
    use_placeholder "$str_root"
    expect "placeholder's own import" fail "$str_root" "pkg._internal.utils.typing"
    rm -rf "$str_root"
}

test_unreachable_util_is_reported_not_failed() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    expect "unreachable util, report-only" pass "$str_root" "pkg._internal.utils.unused"
    expect "dep only the unreachable util uses" pass "$str_root" "import: numpy"
    expect_absent "dep a reachable module also uses" "$str_root" "dateutil"
    expect_absent "stdlib import" "$str_root" "json"
    rm -rf "$str_root"
}

test_unreachable_util_fails_strict() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    expect "unreachable util, --strict" fail "$str_root" "pkg._internal.utils.unused" --strict
    rm -rf "$str_root"
}

test_allowlisted_util_passes_strict() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    printf 'pkg._internal.utils.unused | loaded by importlib\n' > "$str_root/.unreachable-modules.txt"
    expect "allowlisted util, --strict" pass "$str_root" "0 unreachable" --strict
    rm -rf "$str_root"
}

test_allowlisted_util_imports_count_as_live() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    printf 'pkg._internal.utils.unused | loaded by importlib\n' > "$str_root/.unreachable-modules.txt"
    printf 'import dateutil\n' > "$str_root/src/pkg/_internal/utils/other.py"
    expect "non-allowlisted residue still reported" pass "$str_root" "pkg._internal.utils.other"
    expect_absent "allowlisted util's own import" "$str_root" "numpy"
    rm -rf "$str_root"
}

test_allowlist_only_failure_prints_summary() {
    local str_root
    str_root="$(make_project)"
    printf 'pkg._internal.utils.gone | loaded by importlib\n' > "$str_root/.unreachable-modules.txt"
    expect "allowlist-only failure, --strict" fail "$str_root" "❌ 1 allowlist problem(s)" --strict
    rm -rf "$str_root"
}

test_dep_shared_with_dead_module_is_reported() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    printf 'import numpy\n' > "$str_root/src/pkg/_internal/dead_config.py"
    expect "dep shared only with another dead module" pass "$str_root" "import: numpy"
    rm -rf "$str_root"
}

test_allowlist_entry_without_reason_fails_strict() {
    local str_root
    str_root="$(make_project)"
    add_unused_util "$str_root"
    printf 'pkg._internal.utils.unused\n' > "$str_root/.unreachable-modules.txt"
    expect "reasonless allowlist entry, report-only" pass "$str_root" "has no reason"
    expect "reasonless allowlist entry, --strict" fail "$str_root" "has no reason" --strict
    rm -rf "$str_root"
}

test_stale_allowlist_entry_fails_strict() {
    local str_root
    str_root="$(make_project)"
    printf 'pkg._internal.utils.gone | loaded by importlib\n' > "$str_root/.unreachable-modules.txt"
    expect "stale allowlist entry, --strict" fail "$str_root" "matches no unreachable module" --strict
    rm -rf "$str_root"
}

test_empty_src_fails() {
    local str_root
    str_root="$(mktemp -d -p "$TMP_ROOT")"
    expect "no module under src" fail "$str_root" "no module"
    rm -rf "$str_root"
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
    print_status "success" "template residue gate: all checks passed"
}

main "$@"

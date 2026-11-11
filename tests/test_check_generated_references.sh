#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHECK="$REPO_ROOT/bin/ci/check_generated_references.sh"
int_failures=0

make_project() {
    local str_dir
    str_dir="$(mktemp -d)"
    mkdir -p "$str_dir/docs" "$str_dir/bin" "$str_dir/.github/workflows"
    printf 'nav:\n  - Home: index.md\n  - Incidents: incidents.md\ntheme:\n  name: material\n' \
        >"$str_dir/mkdocs.yml"
    touch "$str_dir/docs/index.md" "$str_dir/docs/incidents.md" \
        "$str_dir/bin/a.sh" "$str_dir/bin/b.py" "$str_dir/bin/c.sh"
    printf '[tool.poe.tasks.a]\ncmd = "bash bin/a.sh"\n' >"$str_dir/poe_tasks.toml"
    printf 'repos:\n  - hooks:\n      - entry: python bin/b.py\n' >"$str_dir/.pre-commit-config.yaml"
    printf 'jobs:\n  j:\n    steps:\n      - run: bash bin/c.sh\n' \
        >"$str_dir/.github/workflows/ci.yml"
    printf '%s' "$str_dir"
}

expect() {
    local str_desc="$1" str_want="$2" str_needle="$3" str_victim="$4"
    local str_dir str_got="pass" str_out
    str_dir="$(make_project)"
    [ -z "$str_victim" ] || rm "$str_dir/$str_victim"
    str_out="$(bash "$CHECK" --project "$str_dir" 2>&1)" || str_got="fail"
    rm -rf "$str_dir"
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

expect "complete tree passes" pass "" ""
expect "missing nav page fails" fail "docs/incidents.md" docs/incidents.md
expect "missing poe script fails" fail "bin/a.sh" bin/a.sh
expect "missing pre-commit script fails" fail "bin/b.py" bin/b.py
expect "missing workflow script fails" fail "bin/c.sh" bin/c.sh

expect_dir() {
    local str_desc="$1" str_dir="$2" str_got="pass"
    bash "$CHECK" --project "$str_dir" >/dev/null 2>&1 || str_got="fail"
    [ "$str_got" = "fail" ] && echo "ok: $str_desc" || {
        echo "FAIL: $str_desc -> pass (expected fail)" >&2
        int_failures=$((int_failures + 1))
    }
}

str_empty="$(mktemp -d)"
expect_dir "missing project dir fails" "$str_empty/nonexistent"
expect_dir "empty project dir fails" "$str_empty"
rm -rf "$str_empty"

expect_extra() {
    local str_desc="$1" str_want="$2" str_file="$3" str_body="$4" str_dir str_got="pass"
    str_dir="$(make_project)"
    mkdir -p "$(dirname "$str_dir/$str_file")"
    printf '%s' "$str_body" >"$str_dir/$str_file"
    bash "$CHECK" --project "$str_dir" >/dev/null 2>&1 || str_got="fail"
    rm -rf "$str_dir"
    if [ "$str_got" = "$str_want" ]; then
        echo "ok: $str_desc"
    else
        echo "FAIL: $str_desc -> $str_got (expected $str_want)" >&2
        int_failures=$((int_failures + 1))
    fi
}

expect_extra "package.json reference to a missing script fails" fail package.json '{"scripts":{"a":"bash bin/nope.sh"}}'
expect_extra "Makefile reference to a missing script fails" fail Makefile $'a:\n\tbash bin/nope.sh\n'
expect_extra "make/*.mk reference to a missing script fails" fail make/x.mk $'a:\n\tbash bin/nope.sh\n'
expect_extra "composite action reference to a missing script fails" fail .github/actions/x/action.yml 'run: bash bin/nope.sh'
expect_extra ".yaml workflow reference to a missing script fails" fail .github/workflows/y.yaml 'run: bash bin/nope.sh'
expect_extra "commented-out reference is ignored" pass Makefile $'# bin/nope.sh\n'
expect_extra "nav page under a non-default docs_dir is found" fail mkdocs.yml $'docs_dir: site\nnav:\n  - A: index.md\n'

str_noref="$(mktemp -d)"
printf 'site_name: x\n' >"$str_noref/mkdocs.yml"
expect_dir "a project with no extracted reference fails" "$str_noref"
rm -rf "$str_noref"

str_got="pass"
bash "$CHECK" --generated --skeleton no-such-skeleton >/dev/null 2>&1 || str_got="fail"
[ "$str_got" = "fail" ] && echo "ok: unknown skeleton fails" || {
    echo "FAIL: unknown skeleton passed" >&2
    int_failures=$((int_failures + 1))
}

[ "$int_failures" -eq 0 ]

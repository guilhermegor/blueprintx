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
    local str_desc="$1" str_dir="$2" str_got="pass" str_out
    str_out="$(bash "$CHECK" --project "$str_dir" 2>&1)" || str_got="fail"
    printf '%s' "$str_out" | grep -qE 'ERROR: .*(no project directory|nothing was checked)' || str_got="pass"
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
    local str_desc="$1" str_want="$2" str_file="$3" str_body="$4" str_needle="${5:-nope.sh}" str_diag="${6:-never copied}" str_dir str_got="pass" str_out
    str_dir="$(make_project)"
    mkdir -p "$(dirname "$str_dir/$str_file")"
    printf '%s' "$str_body" >"$str_dir/$str_file"
    str_out="$(bash "$CHECK" --project "$str_dir" 2>&1)" || str_got="fail"
    rm -rf "$str_dir"
    if [ "$str_got" = "fail" ] && ! printf '%s' "$str_out" | grep -qE "ERROR: .*$str_needle.*$str_diag"; then
        echo "FAIL: $str_desc -> failed without a gate message: $str_out" >&2
        int_failures=$((int_failures + 1))
    elif [ "$str_got" = "$str_want" ]; then
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
expect_extra "Makefile recipe tab form is scanned" fail Makefile $'a:\n\tbin/nope.sh\n'
expect_extra "inline comment naming a missing script is ignored" pass poe_tasks.toml $'[tool.poe.tasks.a]\ncmd = "bash bin/a.sh" # replaces bin/old.sh\n'
expect_extra "hash inside a quoted string does not hide a later reference" fail .github/workflows/q.yml $'run: |\n  echo " # label"; bash bin/nope.sh\n'
expect_extra "URL in a nav inline comment does not hide a missing page" fail mkdocs.yml $'nav:\n  - Incidents: gone.md # https://example.com/x\n' gone.md
expect_extra "escaped quote does not end a quoted value early" fail .github/workflows/e.yml $'run: |\n  echo "escaped \\" # label"; bash bin/nope.sh\n'
expect_extra "quoted external nav target is not a local page" pass mkdocs.yml $'nav:\n  - Home: index.md\n  - Source: \'https://example.com/README.md\'\n  - Other: "https://example.com/X.md"\n' index.md
LC_ALL=C expect_extra "accented nav filename is matched whole" fail mkdocs.yml $'nav:\n  - Guia: guia-avançado.md\n' 'guia-avançado.md'
expect_extra "spaced nav filename is matched whole" fail mkdocs.yml $'nav:\n  - Guide: my guide.md\n' 'my guide.md'
expect_extra "apostrophe in prose does not hide the comment strip" pass .github/workflows/p.yml $'jobs:\n  j:\n    steps:\n      - name: Don\x27t skip # see bin/old.sh\n        run: bash bin/a.sh\n' old.sh
expect_extra "nav extractor matching nothing fails even if scripts match" fail mkdocs.yml $'nav:\n  - Home: ~\n' 'mkdocs.yml' 'nothing was checked'
expect_extra "nav title containing a colon keeps the page name" fail mkdocs.yml $'nav:\n  - "Guide: intro": guide.md\n' 'guide.md'
expect_extra "quoted local nav page is matched whole" fail mkdocs.yml $'nav:\n  - Home: "gone.md"\n  - Two: \'two.md\'\n' 'gone.md'
expect_extra "yaml anchor before a nav page is not part of the name" fail mkdocs.yml $'nav:\n  - &home gone.md\n' 'docs/gone.md'
expect_extra "double quote after a word still opens a quoted span" fail .github/workflows/w.yml $'run: |\n  echo prefix" # text"; bash bin/nope.sh\n'
expect_extra "anchor before a quoted nav page is consumed" fail mkdocs.yml $'nav:\n  - Home: &home "gone.md"\n' 'docs/gone.md'
expect_extra "single quote closed later on the line still hides a comment span" fail .github/workflows/s.yml $'run: |\n  echo prefix\x27 # text\x27; bash bin/nope.sh\n'
expect_extra "colon inside a quoted nav page is kept" fail mkdocs.yml $'nav:\n  - Guide: "part: one.md"\n' 'docs/part: one.md'
expect_extra "poe_tasks fragment reference to a missing script fails" fail poe_tasks.test.toml $'[tool.poe.tasks.t]\ncmd = "bash bin/nope.sh"\n'
expect_extra "commented-out reference is ignored" pass Makefile $'# bin/nope.sh\n'
expect_extra "nav page missing under a non-default docs_dir fails" fail mkdocs.yml $'docs_dir: site\nnav:\n  - A: index.md\n' site/index.md
expect_extra ".vscode/tasks.json reference to a missing script is scanned" fail .vscode/tasks.json '{"command":"bash bin/nope.sh"}'

str_site="$(make_project)"
mkdir -p "$str_site/site" && touch "$str_site/site/index.md" "$str_site/site/incidents.md"
printf 'docs_dir: site\nnav:\n  - A: index.md\n  - B: incidents.md\n' >"$str_site/mkdocs.yml"
bash "$CHECK" --project "$str_site" >/dev/null 2>&1 && echo "ok: nav pages found under a non-default docs_dir pass" || {
    echo "FAIL: non-default docs_dir positive case failed" >&2
    int_failures=$((int_failures + 1))
}
rm -rf "$str_site"

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

str_cwd="$(mktemp -d)"
touch "$str_cwd/.log"
str_proj="$(make_project)"
(cd "$str_cwd" && bash "$CHECK" --project "$str_proj" >/dev/null 2>&1) || true
if [ -e "$str_cwd/.log" ]; then
    echo "ok: --project leaves a .log in the working directory alone"
else
    echo "FAIL: --project deleted ./.log" >&2
    int_failures=$((int_failures + 1))
fi
rm -rf "$str_cwd" "$str_proj"

[ "$int_failures" -eq 0 ]

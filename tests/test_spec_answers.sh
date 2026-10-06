#!/bin/bash
# Should-fail regression tests for the --spec flow (blueprintx#629, after #525/#481).
#
# Each case guards one defect that shipped in #525 and was found only after merge:
#   - spec_yn turned any unrecognised value (a typo such as `yse`) into "n";
#   - `--spec` returned before the --dev / --clean branch, so both flags were ignored;
#   - a skeleton with no prompt map ran its scaffold with interactive prompts.
# The dangerous direction is a FALSE PASS, so every refusal is asserted by the message that
# names the cause, not by a bare nonzero exit (which also describes a crash).
#
# Usage: bash tests/test_spec_answers.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# git exports GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE to a pre-commit hook. A scaffold runs
# `git init` + `git commit`, which would then act on the CALLER'S repository: measured, a
# scaffold started by this very hook rewrote the branch being committed. Clear every one.
while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
    echo "FAIL ($1): $2"
    int_failures=$((int_failures + 1))
}

write_spec() {
    # write_spec <name> <skeleton> [extra key=value lines...]; prints the file path.
    local name="$1" skeleton="$2"
    local file="$WORK_DIR/$name.spec"
    shift 2
    {
        printf 'project_name=spec-probe\nproject_description=probe\nlanguage=python\n'
        printf 'skeleton=%s\nlicense=MIT\ngithub_username=ci-bot\n' "$skeleton"
        printf '%s\n' "$@"
    } >"$file"
    echo "$file"
}

run_blueprintx() {
    # run_blueprintx <args...>: stdin closed, run from the sandbox, temp roots confined to it.
    (cd "$WORK_DIR" && TMPDIR="$WORK_DIR" bash "$REPO_ROOT/bin/blueprintx.sh" "$@" 2>&1 </dev/null)
}

yn_in_subshell() {
    # yn_in_subshell <file> <key> <default>: prints "<stdout>|<status>|<stderr>".
    bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        out="$(spec_yn "$2" "$3" "$4" 2>"$5")"; echo "$out|$?|$(cat "$5")"' _ \
        "$REPO_ROOT" "$1" "$2" "$3" "$WORK_DIR/yn.err"
}

test_spec_yn_accepts_the_documented_forms() {
    local file="$WORK_DIR/forms.spec" str_form bool_bad=0
    for str_form in y Y yes YES Yes true TRUE; do
        printf 'flag=%s\n' "$str_form" >"$file"
        [ "$(yn_in_subshell "$file" flag n | cut -d'|' -f1-2)" = "y|0" ] || bool_bad=1
    done
    for str_form in n N no NO false FALSE; do
        printf 'flag=%s\n' "$str_form" >"$file"
        [ "$(yn_in_subshell "$file" flag y | cut -d'|' -f1-2)" = "n|0" ] || bool_bad=1
    done
    : >"$file"
    [ "$(yn_in_subshell "$file" flag y | cut -d'|' -f1-2)" = "y|0" ] || bool_bad=1
    if [ "$bool_bad" -eq 0 ]; then
        pass "spec_yn accepts y/yes/true and n/no/false in any case, empty means the default"
    else
        fail "spec_yn forms" "a documented value was not normalised correctly"
    fi
}

test_spec_yn_rejects_a_typo_naming_the_key() {
    local file="$WORK_DIR/typo.spec" str_res
    printf 'webhook=yse\n' >"$file"
    str_res="$(yn_in_subshell "$file" webhook n)"
    if [[ "$str_res" == "|1|"*"'webhook'"*"'yse'"* ]]; then
        pass "spec_yn rejects 'yse' with the key and value named, and prints no answer"
    else
        fail "spec_yn typo" "got: $str_res"
    fi
}

test_validate_answers_reports_every_bad_key() {
    local file out
    file="$(write_spec multi-bad lib-minimal "otel=maybe" "docker_compose=yse")"
    out="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        spec_validate_answers lib-minimal "$2"' _ "$REPO_ROOT" "$file" 2>&1)"
    if [[ "$out" == *"'otel'"* && "$out" == *"'docker_compose'"* ]]; then
        pass "spec_validate_answers names every bad key, not only the first"
    else
        fail "validate all bad keys" "got: $out"
    fi
}

test_bad_yn_stops_before_anything_is_created() {
    local file root out
    root="$WORK_DIR/bad-yn-root"
    file="$(write_spec bad-yn lib-minimal "project_root=$root" "otel=yse")"
    out="$(run_blueprintx new --spec "$file")"
    if [[ "$out" == *"'otel' must be"* && ! -e "$root/spec-probe" ]]; then
        pass "a bad y/n value refuses the run and creates nothing"
    else
        fail "bad y/n refusal" "project dir exists or message missing: ${out: -300}"
    fi
}

test_unmapped_skeleton_is_refused_before_creating_anything() {
    local file root out
    root="$WORK_DIR/unmapped-root"
    file="$(write_spec unmapped react-spa-webpack "project_root=$root")"
    sed -i 's/^language=python/language=typescript/' "$file"
    out="$(run_blueprintx new --spec "$file")"
    if [[ "$out" == *"has no named-key prompt map"* && ! -e "$root" ]]; then
        pass "a skeleton with no prompt map is refused before any directory is made"
    else
        fail "unmapped skeleton" "root exists or message missing: ${out: -300}"
    fi
}

test_dev_clean_uses_a_temp_root_and_removes_it() {
    local file root out str_temp
    root="$WORK_DIR/proot-clean"
    file="$(write_spec dev-clean lib-minimal "project_root=$root")"
    out="$(run_blueprintx new --spec "$file" --dev --clean)"
    str_temp="$(sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$out" | tr -d '\r' | tail -1)"
    str_temp="$(sed 's/\x1b\[[0-9;]*m//g' <<<"$str_temp")"
    if [ -n "$str_temp" ] && [ ! -e "$str_temp" ] && [ ! -e "$root" ]; then
        pass "--spec --dev --clean scaffolds into a temp root, ignores project_root, and cleans up"
    else
        fail "--dev --clean" "temp='$str_temp' exists=$([ -e "$str_temp" ] && echo yes || echo no) root-made=$([ -e "$root" ] && echo yes || echo no)"
    fi
}

test_dev_without_clean_preserves_the_temp_root() {
    local file root out str_temp
    root="$WORK_DIR/proot-keep"
    file="$(write_spec dev-keep lib-minimal "project_root=$root")"
    out="$(run_blueprintx new --spec "$file" --dev)"
    str_temp="$(sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$out" | sed 's/\x1b\[[0-9;]*m//g' | tail -1)"
    if [ -n "$str_temp" ] && [ -d "$str_temp/spec-probe" ] && [ ! -e "$root" ]; then
        pass "--spec --dev keeps the temp root and the project inside it"
    else
        fail "--dev" "temp='$str_temp' project-in-temp=$([ -d "$str_temp/spec-probe" ] && echo yes || echo no)"
    fi
}

main() {
    test_spec_yn_accepts_the_documented_forms
    test_spec_yn_rejects_a_typo_naming_the_key
    test_validate_answers_reports_every_bad_key
    test_bad_yn_stops_before_anything_is_created
    test_unmapped_skeleton_is_refused_before_creating_anything
    test_dev_clean_uses_a_temp_root_and_removes_it
    test_dev_without_clean_preserves_the_temp_root

    if [ "$int_failures" -eq 0 ]; then
        echo "All --spec regression tests passed."
        exit 0
    fi
    echo "$int_failures --spec regression test(s) FAILED."
    exit 1
}

main

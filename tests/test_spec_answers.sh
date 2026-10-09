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
    # The language defaults to python; set SPEC_LANGUAGE for a non-Python skeleton.
    local name="$1" skeleton="$2"
    local file="$WORK_DIR/$name.spec"
    shift 2
    {
        printf 'project_name=spec-probe\nproject_description=probe\nlanguage=%s\n' "${SPEC_LANGUAGE:-python}"
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
    local file root out int_rc
    root="$WORK_DIR/bad-yn-root"
    file="$(write_spec bad-yn lib-minimal "project_root=$root" "otel=yse")"
    out="$(run_blueprintx new --spec "$file")"
    int_rc=$?
    if [ "$int_rc" -ne 0 ] && [[ "$out" == *"'otel' must be"* && ! -e "$root" ]]; then
        pass "a bad y/n value refuses the run and creates nothing"
    else
        fail "bad y/n refusal" "rc=$int_rc, root exists or message missing: ${out: -300}"
    fi
}

test_unmapped_skeleton_is_refused_before_creating_anything() {
    local file root out int_rc
    root="$WORK_DIR/unmapped-root"
    file="$(SPEC_LANGUAGE=typescript write_spec unmapped react-spa-webpack "project_root=$root")"
    out="$(run_blueprintx new --spec "$file")"
    int_rc=$?
    if [ "$int_rc" -ne 0 ] && [[ "$out" == *"has no named-key prompt map"* && ! -e "$root" ]]; then
        pass "a skeleton with no prompt map is refused before any directory is made"
    else
        fail "unmapped skeleton" "rc=$int_rc, root exists or message missing: ${out: -300}"
    fi
}

prompt_sequence() {
    # prompt_sequence <scaffold script>: the prompt calls main() makes, in order.
    grep -E '^    (prompt_[a-z_]+|scaffold_prompt_review_bot_roster)$' "$1" | tr -d ' '
}

test_api_service_asks_the_same_prompts_as_the_ddd_tiers() {
    # api-service-native-db borrows the DDD key map (blueprintx#668). That is only correct
    # while the two scaffolds ask the same prompts in the same order, so pin the claim: a
    # prompt added to one script must fail here rather than misalign every stored answer.
    local str_api str_ddd
    str_api="$(prompt_sequence "$REPO_ROOT/bin/scaffold/python_api_service.sh")"
    str_ddd="$(prompt_sequence "$REPO_ROOT/bin/scaffold/python_ddd_service.sh")"
    if [ -n "$str_api" ] && [ "$str_api" = "$str_ddd" ]; then
        pass "api-service and DDD scaffolds ask the same prompts in the same order"
    else
        fail "prompt order" "api: [$(echo "$str_api" | tr '\n' ' ')] ddd: [$(echo "$str_ddd" | tr '\n' ' ')]"
    fi
}

test_api_service_storage_answer_reaches_the_storage_prompt() {
    # The point of the map: storage=y must land on the SECOND line the scaffold reads
    # (after docker_compose), exactly as for the DDD tiers.
    local file str_stream
    file="$(write_spec api-storage api-service-native-db "storage=y")"
    str_stream="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        spec_skeleton_supported api-service-native-db && spec_stdin_for_skeleton api-service-native-db "$2"' \
        _ "$REPO_ROOT" "$file" | sed -n 2p)"
    if [ "$str_stream" = "y" ]; then
        pass "storage=y is the second answer emitted for api-service-native-db"
    else
        fail "api storage answer" "second stdin line was '$str_stream', expected 'y'"
    fi
}

test_dev_clean_uses_a_temp_root_and_removes_it() {
    local file root out str_temp int_rc
    root="$WORK_DIR/proot-clean"
    file="$(write_spec dev-clean lib-minimal "project_root=$root")"
    out="$(run_blueprintx new --spec "$file" --dev --clean)"
    int_rc=$?
    str_temp="$(sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$out" | tr -d '\r' | tail -1)"
    str_temp="$(sed 's/\x1b\[[0-9;]*m//g' <<<"$str_temp")"
    if [ "$int_rc" -eq 0 ] && [[ "$str_temp" == "$WORK_DIR"/* ]] && [ ! -e "$str_temp" ] && [ ! -e "$root" ] \
        && [[ "$out" == *"deleted on exit"* ]]; then
        pass "--spec --dev --clean scaffolds into a temp root, ignores project_root, cleans up, and says so"
    else
        fail "--dev --clean" "rc=$int_rc temp='$str_temp' exists=$([ -e "$str_temp" ] && echo yes || echo no) root-made=$([ -e "$root" ] && echo yes || echo no)"
    fi
}

test_dev_without_clean_preserves_the_temp_root() {
    local file root out str_temp int_rc
    root="$WORK_DIR/proot-keep"
    file="$(write_spec dev-keep lib-minimal "project_root=$root")"
    out="$(run_blueprintx new --spec "$file" --dev)"
    int_rc=$?
    str_temp="$(sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$out" | sed 's/\x1b\[[0-9;]*m//g' | tail -1)"
    if [ "$int_rc" -eq 0 ] && [[ "$str_temp" == "$WORK_DIR"/* ]] && [ -d "$str_temp/spec-probe" ] && [ ! -e "$root" ]; then
        pass "--spec --dev keeps the temp root and the project inside it"
    else
        fail "--dev" "rc=$int_rc temp='$str_temp' project-in-temp=$([ -d "$str_temp/spec-probe" ] && echo yes || echo no)"
    fi
}

test_bad_docs_locale_stops_before_anything_is_created() {
    local file root out int_rc
    root="$WORK_DIR/bad-locale-root"
    file="$(write_spec bad-locale lib-minimal "project_root=$root" "docs_locale=pt-br")"
    out="$(run_blueprintx new --spec "$file")"
    int_rc=$?
    if [ "$int_rc" -ne 0 ] && [[ "$out" == *"'docs_locale' must be en or pt-BR"* && ! -e "$root" ]]; then
        pass "an unknown docs_locale refuses the run, naming the key, and creates nothing"
    else
        fail "bad docs_locale refusal" "rc=$int_rc, root exists or message missing: ${out: -300}"
    fi
}

# Reads the generated mkdocs.yml: the placeholder only renders when DOCS_LOCALE reaches the scaffold.
spec_docs_language() {
    # spec_docs_language <name> [extra spec lines...]; prints the `language:` the project got.
    local name="$1" file out str_temp
    shift
    file="$(write_spec "$name" lib-minimal "$@")"
    out="$(run_blueprintx new --spec "$file" --dev)"
    str_temp="$(sed -n 's/.*using temp root \(.*\)$/\1/p' <<<"$out" | sed 's/\x1b\[[0-9;]*m//g' | tail -1)"
    sed -n 's/^  language: //p' "$str_temp/spec-probe/mkdocs.yml" 2>/dev/null
}

test_docs_locale_reaches_the_scaffold() {
    local str_got
    str_got="$(spec_docs_language docs-pt "docs_locale=pt-BR")"
    if [ "$str_got" = "pt-BR" ]; then
        pass "docs_locale=pt-BR in a spec renders language: pt-BR in the generated mkdocs.yml"
    else
        fail "docs_locale pass-through" "generated mkdocs.yml language='$str_got' (expected pt-BR)"
    fi
}

test_absent_docs_locale_defaults_to_en() {
    local str_got
    str_got="$(spec_docs_language docs-default)"
    if [ "$str_got" = "en" ]; then
        pass "a spec with no docs_locale renders language: en, the prompt's default"
    else
        fail "docs_locale default" "generated mkdocs.yml language='$str_got' (expected en)"
    fi
}

test_spec_values_are_trimmed_so_a_crlf_spec_works() {
    local file="$WORK_DIR/crlf.spec" str_yn str_license
    printf 'otel=yes\r\nlicense=MIT \r\n' >"$file"
    str_yn="$(yn_in_subshell "$file" otel n | cut -d'|' -f1-2)"
    str_license="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        printf "<%s>" "$(spec_get "$2" license)"' _ "$REPO_ROOT" "$file")"
    if [ "$str_yn" = "y|0" ] && [ "$str_license" = "<MIT>" ]; then
        pass "a CRLF spec: 'yes\\r' reads as y and 'MIT \\r' as MIT"
    else
        fail "CRLF trim" "yn=$str_yn license=$str_license"
    fi
}

test_yn_keys_read_by_callers_match_the_key_map() {
    local str_called str_mapped str_unparsed
    # A call site the sed below cannot read (a variable default, two calls on one line) would
    # escape the comparison, so any such line fails the test. The validator's generic call is
    # the one allowed exception.
    str_unparsed="$(grep -n 'spec_yn "\$' "$REPO_ROOT/bin/lib/spec.sh" \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -v '"\$key" "\$default"' \
        | grep -vE '^[0-9]+:[^#]*spec_yn "\$[a-z0-9]*" [a-z_]+ [yn]([^a-z_]|$)' \
        ; grep -n 'spec_yn .*spec_yn ' "$REPO_ROOT/bin/lib/spec.sh")" || true
    if [ -n "$str_unparsed" ]; then
        fail "key map vs callers" "call site(s) the check cannot parse: $str_unparsed"
        return
    fi
    # Every `spec_yn "$x" <key> <default>` call site in the answer emitters, as "key:default".
    str_called="$(sed -n '/^[[:space:]]*#/d; s/.*spec_yn "\$[a-z0-9]*" \([a-z_]*\) \([yn]\).*/\1:\2/p' "$REPO_ROOT/bin/lib/spec.sh" | sort -u)"
    # Every y/n entry of the key map across all supported skeletons.
    str_mapped="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        for sk in $_SPEC_SUPPORTED_SKELETONS; do _spec_key_map "$sk"; done' _ "$REPO_ROOT" \
        | grep -E ':[yn]$' | sort -u)"
    if [ -n "$str_called" ] && [ "$str_called" = "$str_mapped" ]; then
        pass "the y/n keys the emitters read are exactly the y/n entries of the key map"
    else
        fail "key map vs callers" "only in callers: $(comm -23 <(echo "$str_called") <(echo "$str_mapped") | tr '\n' ' ') only in map: $(comm -13 <(echo "$str_called") <(echo "$str_mapped") | tr '\n' ' ')"
    fi
}

test_skeleton_match_is_exact() {
    local str_res
    str_res="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        for n in "lib-minimal" "ddd-service-native-db ddd-service-orm-db" "lib-minimal " "lib-*" "LIB-MINIMAL" ""; do
            spec_skeleton_supported "$n" && printf "[%s] " "$n"
        done' _ "$REPO_ROOT")"
    if [ "$str_res" = "[lib-minimal] " ]; then
        pass "spec_skeleton_supported accepts a supported name only, not two joined by a space"
    else
        fail "exact skeleton match" "accepted: $str_res"
    fi
}

test_a_failed_answer_stream_stops_the_scaffold_flow() {
    local str_res
    str_res="$(bash -c '
        str_repo="$1" str_stub="$2"
        set --
        source "$str_repo/bin/blueprintx.sh"
        mkdir -p "$str_stub/templates/fake"
        printf "scaffold=fake.sh\n" >"$str_stub/templates/fake/skeleton.meta"
        printf "touch \"%s/scaffold-ran\"\n" "$str_stub" >"$str_stub/fake.sh"
        TEMPLATES_ROOT="$str_stub/templates" BLUEPRINTX_ROOT="$str_stub"
        SKELETON_CHOICE=fake SPEC_FILE=none PROJECT_ROOT="$str_stub" PROJECT_NAME=p PROJECT_DESCRIPTION=d
        LICENSE_CHOICE=MIT DOCS_LOCALE=en
        spec_stdin_for_skeleton() { return 1; }
        scaffold_from_spec' _ "$REPO_ROOT" "$WORK_DIR/stream" 2>&1)" || true
    if [[ "$str_res" == *"could not resolve the answers for 'fake'"* ]] \
        && [ ! -e "$WORK_DIR/stream/scaffold-ran" ]; then
        pass "a failing answer stream stops the flow before the scaffold ever runs"
    else
        fail "answer stream status" "got: ${str_res: -300}"
    fi
}

main() {
    test_spec_yn_accepts_the_documented_forms
    test_spec_yn_rejects_a_typo_naming_the_key
    test_validate_answers_reports_every_bad_key
    test_bad_yn_stops_before_anything_is_created
    test_unmapped_skeleton_is_refused_before_creating_anything
    test_api_service_asks_the_same_prompts_as_the_ddd_tiers
    test_api_service_storage_answer_reaches_the_storage_prompt
    test_dev_clean_uses_a_temp_root_and_removes_it
    test_dev_without_clean_preserves_the_temp_root
    test_spec_values_are_trimmed_so_a_crlf_spec_works
    test_yn_keys_read_by_callers_match_the_key_map
    test_skeleton_match_is_exact
    test_a_failed_answer_stream_stops_the_scaffold_flow
    test_bad_docs_locale_stops_before_anything_is_created
    test_docs_locale_reaches_the_scaffold
    test_absent_docs_locale_defaults_to_en

    if [ "$int_failures" -eq 0 ]; then
        echo "All --spec regression tests passed."
        exit 0
    fi
    echo "$int_failures --spec regression test(s) FAILED."
    exit 1
}

main

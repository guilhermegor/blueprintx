#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')
export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
    echo "FAIL ($1): $2"
    int_failures=$((int_failures + 1))
}

write_spec() {
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
    (cd "$WORK_DIR" && TMPDIR="$WORK_DIR" bash "$REPO_ROOT/bin/blueprintx.sh" "$@" 2>&1 </dev/null)
}

yn_in_subshell() {
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
    grep -E '^    (prompt_[a-z_]+|scaffold_prompt_review_bot_roster)$' "$1" | tr -d ' '
}

test_api_service_asks_the_same_prompts_as_the_ddd_tiers() {
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

spec_docs_language() {
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
    str_unparsed="$(grep -n 'spec_yn "\$' "$REPO_ROOT/bin/lib/spec.sh" \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -v '"\$key" "\$default"' \
        | grep -vE '^[0-9]+:[^#]*spec_yn "\$[a-z0-9]*" [a-z_]+ [yn]([^a-z_]|$)' \
        ; grep -n 'spec_yn .*spec_yn ' "$REPO_ROOT/bin/lib/spec.sh")" || true
    if [ -n "$str_unparsed" ]; then
        fail "key map vs callers" "call site(s) the check cannot parse: $str_unparsed"
        return
    fi
    str_called="$(sed -n '/^[[:space:]]*#/d; s/.*spec_yn "\$[a-z0-9]*" \([a-z_]*\) \([yn]\).*/\1:\2/p' "$REPO_ROOT/bin/lib/spec.sh" | sort -u)"
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

test_every_python_tier_has_a_prompt_map() {
    local str_res str_meta str_name str_err int_tiers=0
    for str_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
        grep -q '^language=python[[:space:]]*$' "$str_meta" || continue
        int_tiers=$((int_tiers + 1))
        str_name="$(basename "$(dirname "$str_meta")")"
        if ! str_err="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
            spec_skeleton_supported "$2" && spec_stdin_for_skeleton "$2" /dev/null >/dev/null' \
            _ "$REPO_ROOT" "$str_name" 2>&1)"; then
            str_err="${str_err%%$'\n'*}"
            str_res+="$str_name (${str_err:-not in the supported list}) "
        fi
    done
    if [ "$int_tiers" -eq 0 ]; then
        fail "no Python tier found" "templates/*/skeleton.meta matched no language=python"
    elif [ -z "${str_res:-}" ]; then
        pass "every Python tier ($int_tiers) in templates/ has a named-key prompt map (blueprintx#691)"
    else
        fail "unmapped Python tier" "no prompt map for: $str_res"
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

ts_lib_stream() {
    local file
    file="$(SPEC_LANGUAGE=typescript write_spec "stream-$RANDOM" ts-lib "$@")"
    bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        spec_stdin_for_skeleton ts-lib "$2"' _ "$REPO_ROOT" "$file" | paste -sd, -
}

test_ts_lib_answer_stream_order() {
    local str_def str_remote str_full str_priv
    str_def="$(ts_lib_stream)"
    str_remote="$(ts_lib_stream git_remote=y)"
    str_priv="$(ts_lib_stream git_remote=y create_repo=y)"
    str_full="$(ts_lib_stream review_bot_roster=y otel=n git_remote=y create_repo=y \
        repo_visibility=public kanban=y protect_branch=y human_reviewers=y)"
    if [ "$str_def" = "n,n,n" ] && [ "$str_remote" = "n,n,y,n" ] \
        && [ "$str_priv" = "n,n,y,y,2,n,n" ] && [ "$str_full" = "y,n,y,y,1,y,y,y" ]; then
        pass "ts-lib answer stream: roster, otel, git_remote, create_repo, visibility, kanban, protect, reviewers"
    else
        fail "ts-lib stream" "default=$str_def remote=$str_remote private=$str_priv full=$str_full"
    fi
}

test_ts_lib_scaffold_asks_the_prompts_the_stream_assumes() {
    local str_got
    str_got="$(sed -n '/^main() {/,/^}/p' "$REPO_ROOT/bin/scaffold/ts_lib.sh" \
        | grep -E '^    (prompt_[a-z_]+|scaffold_prompt_review_bot_roster)( |$)' \
        | awk '{print $1}' | paste -sd' ' -)"
    if [ "$str_got" = "scaffold_prompt_review_bot_roster prompt_otel prompt_git_remote_setup" ]; then
        pass "ts_lib.sh main() asks roster, otel, git remote in the order the stream is built for"
    else
        fail "ts-lib prompt order" "main() asks: $str_got"
    fi
}

test_ts_lib_remote_keys_defaults() {
    local file str_got
    file="$(SPEC_LANGUAGE=typescript write_spec ts-defaults ts-lib)"
    str_got="$(bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/spec.sh"
        spec_describe_skeleton ts-lib "$2"' _ "$REPO_ROOT" "$file" | grep -E '^(git_remote|create_repo|repo_visibility|kanban|protect_branch|human_reviewers)=' | paste -sd' ' -)"
    if [ "$str_got" = "git_remote=n create_repo=n repo_visibility=private kanban=n protect_branch=n human_reviewers=n" ]; then
        pass "ts-lib remote keys default to no remote, private, no kanban, no protection"
    else
        fail "ts-lib remote defaults" "got: $str_got"
    fi
}

make_gh_stub() {
    mkdir -p "$WORK_DIR/stubbin"
    echo '#!/bin/bash' >"$WORK_DIR/stubbin/gh"
    cat >>"$WORK_DIR/stubbin/gh" <<'STUB'
echo "$*" >>"$STUB_STATE/calls.log"
case "$1 $2" in
    "auth status") [ "${STUB_AUTH:-ok}" = ok ] || exit 1 ;;
    "api user") echo ci-bot ;;
    "repo view")
        case "$*" in *--json*) echo ci-bot/spec-probe; exit 0 ;; esac
        [ "${STUB_REPO_EXISTS:-0}" = 1 ] || [ -e "$STUB_STATE/created" ] && exit 0
        [ "${STUB_VIEW_ERROR:-0}" = 1 ] && { echo "HTTP 502: Bad Gateway" >&2; exit 1; }
        echo "GraphQL: Could not resolve to a Repository with the name '$3'. (repository)" >&2
        exit 1 ;;
    "repo create") touch "$STUB_STATE/created" ;;
    "api -X") case "$*" in *rulesets*) cat >"$STUB_STATE/protection.json" ;; esac ;;
esac
exit 0
STUB
    chmod +x "$WORK_DIR/stubbin/gh" || fail "gh stub" "could not make the stub executable"
}

run_ts_lib_with_gh_stub() {
    local str_name="$1" file
    shift
    local -a list_env=()
    while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do list_env+=("$1"); shift; done
    shift
    STUB_STATE="$WORK_DIR/$str_name-state"
    mkdir -p "$STUB_STATE" "$WORK_DIR/$str_name-remote"
    git init -q --bare "$WORK_DIR/$str_name-remote/spec-probe.git"
    file="$(SPEC_LANGUAGE=typescript write_spec "$str_name" ts-lib "project_root=$WORK_DIR/$str_name-root" "$@")"
    make_gh_stub
    (cd "$WORK_DIR" && env TMPDIR="$WORK_DIR" PATH="$WORK_DIR/stubbin:$PATH" STUB_STATE="$STUB_STATE" \
        GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0="url.$WORK_DIR/$str_name-remote/.insteadOf" \
        GIT_CONFIG_VALUE_0="git@github.com:ci-bot/" GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t \
        GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t GH_PAT_REVIEW_TRIGGER= GITGUARDIAN_API_KEY= \
        "${list_env[@]}" bash "$REPO_ROOT/bin/blueprintx.sh" new --spec "$file" 2>&1 </dev/null) \
        >"$WORK_DIR/$str_name.out"
    INT_RUN_RC=$?
}

test_create_repo_runs_gh_with_the_chosen_visibility_and_protection() {
    local str_calls str_prot int_rc=0
    run_ts_lib_with_gh_stub e2e-priv -- git_remote=y create_repo=y repo_visibility=private \
        protect_branch=y human_reviewers=y
    int_rc=$((int_rc + INT_RUN_RC))
    run_ts_lib_with_gh_stub e2e-pub -- git_remote=y create_repo=y repo_visibility=public \
        protect_branch=y human_reviewers=n
    int_rc=$((int_rc + INT_RUN_RC))
    run_ts_lib_with_gh_stub e2e-nop -- git_remote=y create_repo=y protect_branch=n
    int_rc=$((int_rc + INT_RUN_RC))
    str_calls="$(grep '^repo create' "$WORK_DIR/e2e-priv-state/calls.log" "$WORK_DIR/e2e-pub-state/calls.log" \
        "$WORK_DIR/e2e-nop-state/calls.log" | sed "s|$WORK_DIR/||" | paste -sd'|' -)"
    str_prot="$(tr -d '\n ' <"$WORK_DIR/e2e-priv-state/protection.json" 2>/dev/null)"
    if [[ "$str_calls" == *"e2e-priv-state/calls.log:repo create ci-bot/spec-probe"*"--private"* ]] \
        && [[ "$str_calls" == *"e2e-pub-state/calls.log:repo create ci-bot/spec-probe"*"--public"* ]] \
        && [[ "$str_calls" == *"e2e-nop-state/calls.log:repo create ci-bot/spec-probe"*"--private"* ]] \
        && [[ "$str_prot" == *'"required_approving_review_count":1'* ]] \
        && [[ "$(tr -d '\n ' <"$WORK_DIR/e2e-pub-state/protection.json")" == *'"required_approving_review_count":0'* ]] \
        && ! grep -qhE 'PUT .*branches/.*/protection|--method PUT' "$WORK_DIR"/e2e-*-state/calls.log \
        && [ ! -e "$WORK_DIR/e2e-nop-state/protection.json" ] \
        && [ "$int_rc" -eq 0 ] \
        && [ -d "$WORK_DIR/e2e-priv-root/spec-probe" ] && [ -d "$WORK_DIR/e2e-pub-root/spec-probe" ] \
        && [ -d "$WORK_DIR/e2e-nop-root/spec-probe" ]; then
        pass "create_repo=y: stubbed gh creates --private/--public as asked; protection and reviewers follow the answers"
    else
        fail "create_repo e2e" "calls=$str_calls priv-protection=$str_prot out=$(tail -c 300 "$WORK_DIR/e2e-priv.out")"
    fi
}

test_create_repo_n_never_calls_gh_repo_create() {
    run_ts_lib_with_gh_stub e2e-nocreate -- git_remote=y create_repo=n
    if [ "$INT_RUN_RC" -eq 0 ] && [ -d "$WORK_DIR/e2e-nocreate-root/spec-probe" ] \
        && ! grep -q '^repo create' "$WORK_DIR/e2e-nocreate-state/calls.log" 2>/dev/null; then
        pass "git_remote=y with create_repo=n adds origin but never asks gh to create a repo"
    else
        fail "create_repo=n" "out=$(tail -c 300 "$WORK_DIR/e2e-nocreate.out")"
    fi
}

test_create_repo_preflight_stops_before_any_file_is_written() {
    local str_cause
    for str_cause in "STUB_AUTH=fail|gh CLI" "STUB_REPO_EXISTS=1|already exists" \
        "STUB_VIEW_ERROR=1|not a not-found error"; do
        run_ts_lib_with_gh_stub "pre-${str_cause%%=*}" "${str_cause%%|*}" -- git_remote=y create_repo=y
        local str_name="pre-${str_cause%%=*}"
        if [ "$INT_RUN_RC" -ne 0 ] && [ ! -e "$WORK_DIR/$str_name-root" ] && grep -q "${str_cause##*|}" "$WORK_DIR/$str_name.out" \
            && ! grep -q '^repo create' "$WORK_DIR/$str_name-state/calls.log"; then
            pass "preflight (${str_cause%%|*}) refuses naming the cause; nothing created, no repo create"
        else
            fail "preflight ${str_cause%%|*}" "out=$(tail -c 300 "$WORK_DIR/$str_name.out")"
        fi
    done
}

test_remote_key_validation_names_the_key() {
    local file str_orphan str_vis
    file="$(SPEC_LANGUAGE=typescript write_spec bad-vis ts-lib "project_root=$WORK_DIR/bad-vis-root" \
        git_remote=y create_repo=y repo_visibility=internal)"
    str_vis="$(run_blueprintx new --spec "$file")"
    file="$(SPEC_LANGUAGE=typescript write_spec orphan ts-lib "project_root=$WORK_DIR/orphan-root" \
        create_repo=y)"
    str_orphan="$(run_blueprintx new --spec "$file")"
    if [[ "$str_vis" == *"'repo_visibility' must be public or private, got 'internal'"* ]] \
        && [[ "$str_orphan" == *"'create_repo' is y but 'git_remote' is not"* ]] \
        && [ ! -e "$WORK_DIR/bad-vis-root" ] && [ ! -e "$WORK_DIR/orphan-root" ]; then
        pass "bad repo_visibility and create_repo without git_remote stop the run naming the key"
    else
        fail "remote validation" "vis: ${str_vis: -200} orphan: ${str_orphan: -200}"
    fi
}

test_dry_run_prints_the_remote_answers_and_creates_nothing() {
    local file out
    make_gh_stub
    file="$(SPEC_LANGUAGE=typescript write_spec dry-remote ts-lib "project_root=$WORK_DIR/dry-root" \
        git_remote=y create_repo=y repo_visibility=public protect_branch=y)"
    out="$(STUB_STATE="$WORK_DIR" PATH="$WORK_DIR/stubbin:$PATH" run_blueprintx new --spec "$file" --dry-run)"
    if [[ "$out" == *"repo_slug=ci-bot/spec-probe"* && "$out" == *"repo_visibility=public"* \
        && "$out" == *"protect_branch=y"* ]] && [ ! -e "$WORK_DIR/dry-root" ] \
        && [ ! -e "$WORK_DIR/calls.log" ]; then
        pass "--dry-run prints slug, visibility and protection, creates nothing and never calls gh"
    else
        fail "dry-run remote" "got: ${out: -400}"
    fi
}

main() {
    test_ts_lib_answer_stream_order
    test_ts_lib_scaffold_asks_the_prompts_the_stream_assumes
    test_ts_lib_remote_keys_defaults
    test_create_repo_runs_gh_with_the_chosen_visibility_and_protection
    test_create_repo_n_never_calls_gh_repo_create
    test_create_repo_preflight_stops_before_any_file_is_written
    test_remote_key_validation_names_the_key
    test_dry_run_prints_the_remote_answers_and_creates_nothing
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
    test_every_python_tier_has_a_prompt_map
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

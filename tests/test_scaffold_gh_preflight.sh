#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0
str_out=""
int_rc=0

make_stub() {
    mkdir -p "$WORK_DIR/bin"
    cat >"$WORK_DIR/bin/gh" <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >>"$GH_LOG"
case "$1 $2" in
"api graphql")
    [ -z "${GH_GRAPHQL_ERR:-}" ] || { echo "$GH_GRAPHQL_ERR" >&2; exit 1; } ;;
"api -i")
    [ "${GH_SCOPES_HEADER:-on}" = off ] || printf 'HTTP/2.0 200 OK\r\n%s: %s\r\n\r\n{}\n' "${GH_SCOPES_NAME:-X-Oauth-Scopes}" "${GH_SCOPES-repo, project, read:org}" ;;
"config get") echo "${GH_PROTOCOL:-https}" ;;
"api user")
    [ -z "${GH_USER_ERR:-}" ] || { echo "$GH_USER_ERR" >&2; exit 1; }
    echo "${GH_LOGIN-octo}" ;;
"api rate_limit")
    str_rate="${GH_RATE:-5000 9999999999}"
    case "$*" in *"graphql.reset"*) echo "${str_rate##* }" ;; *) echo "$str_rate" ;; esac ;;
"api users/"*)
    [ -z "${GH_OWNER_ERR:-}" ] || { echo "$GH_OWNER_ERR" >&2; exit 1; }
    echo "User" ;;
"repo view")
    [ -z "${GH_VIEW_ERR:-}" ] || { echo "$GH_VIEW_ERR" >&2; exit 1; }
    echo "${GH_REPO_PRIVATE:-true}" ;;
"label create")
    [ -z "${GH_LABEL_ERR:-}" ] || { echo "$GH_LABEL_ERR" >&2; exit 1; } ;;
"repo create") echo "created" ;;
"project list") echo "${GH_PROJECT_NUMBER:-}" ;;
"project create") echo 7 ;;
"project field-list") case "$*" in *".fields[].name"* | *options*) ;; *) echo PVTSSF_status ;; esac ;;
esac
exit 0
STUB
    chmod +x "$WORK_DIR/bin/gh"
}

run_fn() {
    local str_answers="$1"
    shift
    : >"$WORK_DIR/gh.log"
    str_out="$(
        export GH_LOG="$WORK_DIR/gh.log" PATH="$WORK_DIR/bin:$PATH" GITHUB_USERNAME=octo PROJECT_NAME=widget
        export DEFAULT_GITHUB_USERNAME=octo
        while [ "$#" -gt 0 ] && [[ "$1" == *=* ]]; do
            export "${1?}"
            shift
        done
        # shellcheck source=bin/lib/scaffold_git_remote.sh
        source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"
        printf '%b' "$str_answers" | BLUEPRINTX_STDIN_ANSWERS=1 "$@" 2>&1
    )"
    int_rc=$?
}

fail() {
    print_status "error" "$1"
    int_failures=$((int_failures + 1))
}

expect_stop() {
    [ "$int_rc" -ne 0 ] || fail "$1: expected a nonzero stop, got rc=0"
}

expect_said() {
    grep -qF -- "$2" <<<"$str_out" || fail "$1: output never said '$2': ${str_out: -300}"
}

expect_not_said() {
    ! grep -qF -- "$2" <<<"$str_out" || fail "$1: output must not say '$2'"
}

expect_not_called() {
    ! grep -qF -- "$2" "$WORK_DIR/gh.log" || fail "$1: gh was called with '$2'"
}

test_preflight_rate_limit_prints_the_reset_time() {
    local int_reset=$(($(date +%s) + 840))
    run_fn '' "GH_GRAPHQL_ERR=GraphQL: API rate limit already exceeded" "GH_RATE=0 ${int_reset}" gh_preflight
    expect_stop "rate limit"
    expect_said "rate limit" "retry in 14 min"
    expect_said "rate limit" "after $(date -u -d "@${int_reset}" +%H:%MZ)"
}

test_preflight_secondary_limit_uses_retry_after() {
    run_fn '' "GH_GRAPHQL_ERR=secondary rate limit, Retry-After: 60" gh_preflight
    expect_stop "secondary limit"
    expect_said "secondary limit" "retry in 60 s"
}

test_preflight_unknown_wait_says_so() {
    run_fn '' "GH_GRAPHQL_ERR=API rate limit exceeded" "GH_RATE=oops" gh_preflight
    expect_stop "unknown wait"
    expect_said "unknown wait" "unknown, retry later"
}

test_preflight_stops_on_an_auth_error() {
    run_fn '' "GH_USER_ERR=HTTP 401: Bad credentials" gh_preflight
    expect_stop "auth"
    expect_said "auth" "gh auth login"
    expect_not_said "auth" "retry in"
}

test_preflight_stops_on_a_network_error() {
    run_fn '' "GH_GRAPHQL_ERR=dial tcp: lookup api.github.com: no such host" gh_preflight
    expect_stop "network"
    expect_said "network" "check the connection"
}

test_preflight_stops_when_the_budget_is_too_low() {
    local int_reset=$(($(date +%s) + 600))
    run_fn '' "GH_RATE=10 ${int_reset}" gh_preflight
    expect_stop "low budget"
    expect_said "low budget" "retry in 10 min"
}

test_preflight_stops_on_a_blank_login() {
    run_fn '' "GH_LOGIN=" gh_preflight
    expect_stop "blank login"
    expect_said "blank login" "blank login"
}

test_preflight_passes_on_a_healthy_gh() {
    run_fn '' gh_preflight
    [ "$int_rc" -eq 0 ] || fail "healthy: preflight stopped: $str_out"
    expect_said "healthy" "gh preflight passed"
}

test_preflight_stops_when_the_project_scope_is_missing() {
    run_fn '' "GH_SCOPES=repo, read:org" gh_preflight
    expect_stop "project scope"
    expect_said "project scope" "lacks the 'project' scope"
    expect_said "project scope" "gh auth refresh -s project"
    expect_not_said "project scope" "gh auth refresh -s repo"
    expect_not_said "project scope" "gh preflight passed"
}

test_preflight_names_every_missing_scope() {
    run_fn '' "GH_SCOPES=" gh_preflight
    expect_stop "no scopes"
    expect_said "no scopes" "gh auth refresh -s repo"
    expect_said "no scopes" "gh auth refresh -s project"
}

test_preflight_does_not_match_a_scope_by_substring() {
    run_fn '' "GH_SCOPES=repo, read:project" gh_preflight
    expect_stop "read:project only"
    expect_said "read:project only" "gh auth refresh -s project"
}

test_preflight_skips_the_scope_check_when_none_are_reported() {
    run_fn '' "GH_SCOPES_HEADER=off" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "no header: preflight stopped: $str_out"
    expect_said "no header" "not verified"
}

test_create_repo_never_runs_without_the_project_scope() {
    run_fn 'y\n1\n' "GH_SCOPES=repo" scaffold_create_github_repo "$WORK_DIR"
    expect_stop "create repo scope"
    expect_said "create repo scope" "gh auth refresh -s project"
    expect_not_called "create repo scope" "repo create"
}

test_preflight_reads_the_scopes_header_in_any_casing() {
    run_fn '' "GH_SCOPES_NAME=X-OAUTH-SCOPES" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "upper-case header: preflight stopped: $str_out"
    run_fn '' "GH_SCOPES_NAME=x-oauth-scopes" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "lower-case header: preflight stopped: $str_out"
}

test_preflight_tolerates_any_spacing_in_the_scope_list() {
    run_fn '' "GH_SCOPES=repo,project" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "no spaces: preflight stopped: $str_out"
    run_fn '' "GH_SCOPES= repo ,  project ," gh_preflight
    [ "$int_rc" -eq 0 ] || fail "odd spaces: preflight stopped: $str_out"
}

test_an_https_promotion_requires_the_workflow_scope() {
    local str_cmd='source "$1/bin/lib/common.sh"; source "$1/bin/lib/gh_preflight.sh"; gh_require_workflow_for_https; gh_preflight'
    run_fn '' "GH_SCOPES=repo, project" bash -c "$str_cmd" _ "$REPO_ROOT"
    expect_stop "https promote"
    expect_said "https promote" "gh auth refresh -s workflow"
    run_fn '' "GH_SCOPES=repo, project" "GH_PROTOCOL=ssh" bash -c "$str_cmd" _ "$REPO_ROOT"
    [ "$int_rc" -eq 0 ] || fail "ssh promote: preflight stopped: $str_out"
    grep -q 'gh_require_workflow_for_https' "$REPO_ROOT/bin/promote_offline_to_online.sh" ||
        fail "the promoter never asks for the workflow scope"
}

test_create_repo_never_runs_when_two_boards_share_the_title() {
    run_fn 'y\n1\n' "GH_PROJECT_NUMBER=$(printf '4\n9')" scaffold_create_github_repo "$WORK_DIR"
    expect_stop "early duplicates"
    expect_said "early duplicates" "https://github.com/users/octo/projects/4"
    expect_said "early duplicates" "https://github.com/users/octo/projects/9"
    expect_not_called "early duplicates" "repo create"
}

test_create_repo_never_runs_when_the_preflight_fails() {
    run_fn 'y\n1\n' "GH_GRAPHQL_ERR=API rate limit exceeded" scaffold_create_github_repo "$WORK_DIR"
    expect_stop "create repo"
    expect_not_called "create repo" "repo create"
}

test_visibility_never_defaults_to_public_on_a_failed_read() {
    run_fn '\n' "GH_VIEW_ERR=API rate limit exceeded" scaffold_kanban_visibility octo/widget
    expect_stop "visibility"
    expect_not_said "visibility" "PUBLIC"
    run_fn '\n' scaffold_kanban_visibility octo/widget
    expect_said "private repo" "PRIVATE"
}

test_board_url_never_guesses_the_owner_kind() {
    run_fn '' "GH_OWNER_ERR=API rate limit exceeded" scaffold_kanban_url octo 7
    expect_stop "board url"
    expect_not_said "board url" "github.com/users/"
}

test_a_mid_run_label_failure_stops() {
    run_fn '' "GH_LABEL_ERR=API rate limit exceeded" scaffold_create_house_labels octo/widget
    expect_stop "label"
    expect_said "label" "house label"
    expect_not_said "label" "House labels created"
}

test_a_rerun_completes_without_duplicates() {
    run_fn 'n\n' scaffold_kanban_setup
    [ "$int_rc" -eq 0 ] || fail "rerun: first run stopped: $str_out"
    run_fn '\n\n' "GH_PROJECT_NUMBER=7" scaffold_kanban_setup
    [ "$int_rc" -eq 0 ] || fail "rerun: second run stopped: $str_out"
    expect_not_called "rerun" "project create"
    expect_said "rerun" "already exists (#7)"
    grep -qF -- "project link 7" "$WORK_DIR/gh.log" || fail "rerun: a partial board was never re-linked"
    grep -qF -- "project field-create 7" "$WORK_DIR/gh.log" || fail "rerun: the missing fields were never created"
}

test_a_stop_after_the_repo_exists_does_not_advise_a_plain_rerun() {
    run_fn '' "SCAFFOLD_CREATED_REPO=octo/widget" "GH_LABEL_ERR=boom" scaffold_create_house_labels octo/widget
    expect_stop "created repo"
    expect_said "created repo" "octo/widget already exists on GitHub"
    expect_not_said "created repo" "half-created online project is never acceptable. Re-run"
}

test_graphql_call_sites_match_the_measured_count() {
    local int_sites
    int_sites="$(cat "$REPO_ROOT"/bin/lib/scaffold_kanban.sh "$REPO_ROOT"/bin/lib/scaffold_git_remote.sh \
        "$REPO_ROOT"/bin/lib/scaffold_repo_settings.sh | grep -cE '\bgh (project|repo view|api graphql)')"
    # shellcheck source=bin/lib/gh_preflight.sh
    source "$REPO_ROOT/bin/lib/gh_preflight.sh"
    [ "$int_sites" -eq "$SCAFFOLD_GH_GRAPHQL_SITES" ] ||
        fail "GraphQL call sites are ${int_sites}, SCAFFOLD_GH_GRAPHQL_SITES is ${SCAFFOLD_GH_GRAPHQL_SITES}: re-check SCAFFOLD_GH_GRAPHQL_BUDGET and update both (docs/online-scaffold-gh-preflight.md)"
}

test_no_scaffold_swallows_a_failed_gh_user_read() {
    ! grep -nE 'gh api user[^|]*\|\| *true' "$REPO_ROOT"/bin/scaffold/*.sh "$REPO_ROOT"/bin/promote_offline_to_online.sh ||
        fail "a scaffold still swallows a failed 'gh api user' read with '|| true'"
}

test_stop_message_prints_the_real_rerun_command() {
    local str_spec="$WORK_DIR/my project.spec"
    printf 'project_name=widget\n' >"$str_spec"
    run_fn '' "GH_GRAPHQL_ERR=API rate limit exceeded" "SPEC_FILE=$str_spec" "BLUEPRINTX_ROOT=$REPO_ROOT" \
        bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/gh_preflight.sh"; eval "$(sed -n "/^export_rerun_cmd()/,/^}/p" "$1/bin/blueprintx.sh")"; export_rerun_cmd s r n d; gh_preflight' _ "$REPO_ROOT"
    expect_stop "rerun"
    expect_said "rerun" "Re-run bash $REPO_ROOT/bin/blueprintx.sh new --spec"
    expect_said "rerun" "my\\ project.spec"
    expect_not_said "rerun" "the same blueprintx command"
    run_fn '' "GH_GRAPHQL_ERR=API rate limit exceeded" "SPEC_FILE=" "BLUEPRINTX_ROOT=$REPO_ROOT" "LICENSE_CHOICE=MIT" "DOCS_LOCALE=en" \
        bash -c 'source "$1/bin/lib/common.sh"; source "$1/bin/lib/gh_preflight.sh"; eval "$(sed -n "/^export_rerun_cmd()/,/^}/p" "$1/bin/blueprintx.sh")"; export_rerun_cmd /x/s.sh /p widget "a b"; gh_preflight' _ "$REPO_ROOT"
    expect_said "rerun interactive" "LICENSE_CHOICE=MIT DOCS_LOCALE=en bash /x/s.sh /p widget a\\ b"
}

main() {
    make_stub
    test_preflight_rate_limit_prints_the_reset_time
    test_preflight_secondary_limit_uses_retry_after
    test_preflight_unknown_wait_says_so
    test_preflight_stops_on_an_auth_error
    test_preflight_stops_on_a_network_error
    test_preflight_stops_when_the_budget_is_too_low
    test_preflight_stops_on_a_blank_login
    test_preflight_passes_on_a_healthy_gh
    test_preflight_stops_when_the_project_scope_is_missing
    test_preflight_names_every_missing_scope
    test_preflight_does_not_match_a_scope_by_substring
    test_preflight_skips_the_scope_check_when_none_are_reported
    test_create_repo_never_runs_without_the_project_scope
    test_preflight_reads_the_scopes_header_in_any_casing
    test_preflight_tolerates_any_spacing_in_the_scope_list
    test_an_https_promotion_requires_the_workflow_scope
    test_create_repo_never_runs_when_two_boards_share_the_title
    test_create_repo_never_runs_when_the_preflight_fails
    test_visibility_never_defaults_to_public_on_a_failed_read
    test_board_url_never_guesses_the_owner_kind
    test_a_mid_run_label_failure_stops
    test_a_rerun_completes_without_duplicates
    test_a_stop_after_the_repo_exists_does_not_advise_a_plain_rerun
    test_stop_message_prints_the_real_rerun_command
    test_no_scaffold_swallows_a_failed_gh_user_read
    test_graphql_call_sites_match_the_measured_count
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures failure(s)"
        exit 1
    fi
    print_status "success" "all gh-preflight checks passed"
}

main "$@"

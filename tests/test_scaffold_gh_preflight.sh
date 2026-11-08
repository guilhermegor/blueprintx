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
    [ -z "${GH_GRAPHQL_ERR:-}" ] || { echo "$GH_GRAPHQL_ERR" >&2; exit 1; }
    case "$*" in
    *workflows*) ;;
    *) exit 0 ;;
    esac
    case "$*" in
    *"... on ProjectV2Owner"*"workflows(first:"*"nodes{name enabled}"*) ;;
    *) echo "stub: unexpected GraphQL query: $*" >&2; exit 1 ;;
    esac
    str_expr="."
    while [ "$#" -gt 0 ]; do [ "$1" = "--jq" ] && str_expr="$2"; shift; done
    printf '%b' "${GH_WORKFLOWS-true|Item closed\\ntrue|Pull request merged\\n}" |
        jq -R -s '{data:{repositoryOwner:{projectV2:{workflows:{nodes:(split("\n")|map(select(length>0)|split("|")|{enabled:(.[0]=="true"),name:.[1]}))}}}}}' |
        jq -r "$str_expr" ;;
"api -i")
    [ "${GH_SCOPES_HEADER:-on}" = off ] || printf 'HTTP/2.0 200 OK\r\n%s: %s\r\n\r\n{}\n' "${GH_SCOPES_NAME:-X-Oauth-Scopes}" "${GH_SCOPES-repo, project, read:org}" ;;
"config get") case "$*" in *"-h github.com"*) echo "${GH_HOST_PROTOCOL:-${GH_PROTOCOL:-https}}" ;; *) echo "${GH_PROTOCOL:-https}" ;; esac ;;
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

test_preflight_stops_on_a_non_numeric_budget_or_cost() {
    run_fn '' "SCAFFOLD_GH_GRAPHQL_BUDGET=lots" gh_preflight
    expect_stop "non-numeric budget"
    expect_said "non-numeric budget" "SCAFFOLD_GH_GRAPHQL_BUDGET must be a whole number"
    expect_not_said "non-numeric budget" "gh preflight passed"
    run_fn '' "SCAFFOLD_GH_GRAPHQL_COST=5x" gh_preflight
    expect_stop "non-numeric cost"
    expect_said "non-numeric cost" "SCAFFOLD_GH_GRAPHQL_COST must be a whole number"
    expect_not_said "non-numeric cost" "gh preflight passed"
    run_fn '' "SCAFFOLD_GH_GRAPHQL_COST=0560" gh_preflight
    expect_stop "octal cost"
    expect_said "octal cost" "SCAFFOLD_GH_GRAPHQL_COST must be a whole number"
    run_fn '' "SCAFFOLD_GH_GRAPHQL_COST=500000000" gh_preflight
    expect_stop "cost whose doubled budget overflows the digit cap"
    expect_said "huge cost" "SCAFFOLD_GH_GRAPHQL_COST must be a whole number"
    run_fn '' "SCAFFOLD_GH_GRAPHQL_BUDGET=99999999999999999999" gh_preflight
    expect_stop "overlong budget"
    expect_said "overlong budget" "SCAFFOLD_GH_GRAPHQL_BUDGET must be a whole number"
}

test_preflight_warns_when_the_budget_is_below_one_scaffold() {
    run_fn '' "SCAFFOLD_GH_GRAPHQL_BUDGET=100" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "low override: preflight stopped: $str_out"
    expect_said "low override" "it is in points now, not calls"
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
    run_fn '' "GH_SCOPES=repo, project" "GH_PROTOCOL=https" "GH_HOST_PROTOCOL=ssh" bash -c "$str_cmd" _ "$REPO_ROOT"
    [ "$int_rc" -eq 0 ] || fail "per-host ssh: preflight stopped on the global https value: $str_out"
}

run_promoter_gate() {
    run_fn '' "GH_SCOPES=$1" bash -c '
        source "$1/bin/promote_offline_to_online.sh"
        gh() {
            case "$1 $2" in
            "auth status") return 0 ;;
            "config get") echo https ;;
            "api -i") printf "HTTP/2 200\r\nX-Oauth-Scopes: %s\r\n\r\n{}\n" "$GH_SCOPES" ;;
            "api rate_limit") echo "5000 9999999999" ;;
            "api user") echo octo ;;
            esac
        }
        require_gh_ready' _ "$REPO_ROOT"
}

test_the_promoter_needs_repo_and_workflow_but_not_project() {
    run_promoter_gate "repo, workflow"
    [ "$int_rc" -eq 0 ] || fail "promoter: stopped though it holds repo and workflow: $str_out"
    run_promoter_gate "repo"
    expect_stop "promoter without workflow"
    expect_said "promoter without workflow" "gh auth refresh -s workflow"
    expect_not_said "promoter without workflow" "gh auth refresh -s project"
}

test_an_empty_required_scope_list_opts_out_of_the_check() {
    run_fn '' "SCAFFOLD_GH_REQUIRED_SCOPES=" "GH_SCOPES=" gh_preflight
    [ "$int_rc" -eq 0 ] || fail "opt-out: preflight still stopped: $str_out"
}

test_the_board_title_has_one_definition() {
    local int_defs
    int_defs="$(grep -cE '(%s|\}) kanban' "$REPO_ROOT/bin/lib/scaffold_kanban.sh")"
    [ "$int_defs" -eq 1 ] || fail "the '<project> kanban' title is built in ${int_defs} places, not one helper"
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

test_board_workflows_warn_when_item_closed_is_off() {
    run_fn '' "GH_WORKFLOWS=false|Item closed\\ntrue|Pull request merged" scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows off: must warn, not stop: $str_out"
    expect_said "workflows off" "'Item closed' is off, so closed issues will not move"
    expect_not_said "workflows off" "'Pull request merged' is off"
}

test_board_workflows_silent_when_both_are_on() {
    run_fn '' scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows on: rc=${int_rc}: $str_out"
    expect_not_said "workflows on" "is off"
    expect_not_said "workflows on" "was not found"
    expect_not_said "workflows on" "Could not read"
    expect_not_said "workflows on" "Cards will not move"
}

test_board_workflows_report_a_missing_name_not_an_off_toggle() {
    run_fn '' "GH_WORKFLOWS=true|Item closed archived\\ntrue|Pull request merged" scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows renamed: must warn, not stop: $str_out"
    expect_said "workflows renamed" "'Item closed' was not found under that name"
    expect_not_said "workflows renamed" "'Item closed' is off"
    expect_not_said "workflows renamed" "'Pull request merged'"
}

test_board_workflows_print_the_instruction_when_unreadable() {
    run_fn '' "GH_GRAPHQL_ERR=boom" scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows unreadable: must not stop: $str_out"
    expect_said "workflows unreadable" "enable 'Item closed' and 'Pull request merged'"
    expect_said "workflows unreadable" "cause: other"
}

test_board_workflows_name_the_cause_when_rate_limited() {
    run_fn '' "GH_GRAPHQL_ERR=API rate limit exceeded" scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows rate limited: must not stop: $str_out"
    expect_said "workflows rate limited" "cause: rate"
}

test_board_workflows_empty_list_is_not_unreadable() {
    run_fn '' "GH_WORKFLOWS=" scaffold_kanban_workflows octo 7
    [ "$int_rc" -eq 0 ] || fail "workflows empty: must warn, not stop: $str_out"
    expect_not_said "workflows empty" "Could not read"
    expect_said "workflows empty" "'Item closed' was not found under that name"
}

test_a_fresh_scaffold_pins_the_graphql_cost_and_budget_defaults() {
    local int_calls int_fields
    unset SCAFFOLD_GH_GRAPHQL_COST SCAFFOLD_GH_GRAPHQL_BUDGET SCAFFOLD_GH_GRAPHQL_MEASURED SCAFFOLD_GH_GRAPHQL_SITES
    run_fn 'y\n\n' "GH_PROJECT_NUMBER=" scaffold_kanban_setup
    [ "$int_rc" -eq 0 ] || fail "budget: scaffold stopped: $str_out"
    int_calls="$(grep -cE '^(project|repo view|api graphql)' "$WORK_DIR/gh.log")"
    int_fields="$(grep -c '^project field-list' "$WORK_DIR/gh.log")"
    [ "$int_fields" -eq 3 ] ||
        fail "a fresh scaffold makes ${int_fields} field-list calls (101 points each), the doc's fresh-setup rows say 3"
    # shellcheck source=bin/lib/gh_preflight.sh
    source "$REPO_ROOT/bin/lib/gh_preflight.sh"
    [ "$int_calls" -eq "$SCAFFOLD_GH_GRAPHQL_MEASURED" ] ||
        fail "a fresh scaffold makes ${int_calls} GraphQL-backed gh calls, SCAFFOLD_GH_GRAPHQL_MEASURED is ${SCAFFOLD_GH_GRAPHQL_MEASURED}"
    [ "$SCAFFOLD_GH_GRAPHQL_COST" -eq 560 ] ||
        fail "SCAFFOLD_GH_GRAPHQL_COST default is ${SCAFFOLD_GH_GRAPHQL_COST}, pinned at 560: update the doc table with it"
    [ "$SCAFFOLD_GH_GRAPHQL_BUDGET" -eq 1120 ] ||
        fail "SCAFFOLD_GH_GRAPHQL_BUDGET default is ${SCAFFOLD_GH_GRAPHQL_BUDGET}, pinned at 1120 (2 * cost)"
    unset SCAFFOLD_GH_GRAPHQL_COST SCAFFOLD_GH_GRAPHQL_BUDGET SCAFFOLD_GH_GRAPHQL_MEASURED SCAFFOLD_GH_GRAPHQL_SITES
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
    test_preflight_stops_on_a_non_numeric_budget_or_cost
    test_preflight_warns_when_the_budget_is_below_one_scaffold
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
    test_the_promoter_needs_repo_and_workflow_but_not_project
    test_an_empty_required_scope_list_opts_out_of_the_check
    test_the_board_title_has_one_definition
    test_create_repo_never_runs_when_two_boards_share_the_title
    test_create_repo_never_runs_when_the_preflight_fails
    test_visibility_never_defaults_to_public_on_a_failed_read
    test_board_url_never_guesses_the_owner_kind
    test_a_mid_run_label_failure_stops
    test_a_rerun_completes_without_duplicates
    test_a_stop_after_the_repo_exists_does_not_advise_a_plain_rerun
    test_stop_message_prints_the_real_rerun_command
    test_no_scaffold_swallows_a_failed_gh_user_read
    test_board_workflows_warn_when_item_closed_is_off
    test_board_workflows_silent_when_both_are_on
    test_board_workflows_report_a_missing_name_not_an_off_toggle
    test_board_workflows_print_the_instruction_when_unreadable
    test_board_workflows_name_the_cause_when_rate_limited
    test_board_workflows_empty_list_is_not_unreadable
    test_a_fresh_scaffold_pins_the_graphql_cost_and_budget_defaults
    test_graphql_call_sites_match_the_measured_count
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures failure(s)"
        exit 1
    fi
    print_status "success" "all gh-preflight checks passed"
}

main "$@"

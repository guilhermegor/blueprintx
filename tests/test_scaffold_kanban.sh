#!/bin/bash
# Should-fail regression tests for bin/lib/scaffold_kanban.sh (blueprintx#592).
#
# A stub `gh` on PATH logs every call and answers from environment switches, so the suite needs
# no network and no token. Every refusal is asserted by what the lib said or did not call, and
# every case has a control that does the work, so a lib that silently does nothing cannot pass.
#
# Usage: bash tests/test_scaffold_kanban.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

make_stub() {
    # A `gh` that logs "$*" to $GH_LOG and answers the calls the lib makes.
    mkdir -p "$WORK_DIR/bin"
    cat >"$WORK_DIR/bin/gh" <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >>"$GH_LOG"
jq_arg() {
    while [ "$#" -gt 0 ]; do
        [ "$1" = "--jq" ] && { printf '%s' "$2"; return; }
        shift
    done
}
case "$1 $2" in
"project list")
    str_json="${GH_PROJECTS:-}"
    [ -n "$str_json" ] || str_json='{"projects":[]}'
    jq -r "$(jq_arg "$@")" <<<"$str_json" ;;
"project create")
    if [ -n "${GH_SCOPE_FAIL:-}" ]; then
        echo "error: your authentication token is missing required scopes [project]" >&2
        exit 1
    fi
    echo 7 ;;
"project field-list") echo "PVTSSF_status" ;;
"api graphql") cat >>"$GH_LOG.stdin" ;;
"repo view") echo "${GH_REPO_PRIVATE:-false}" ;;
"api users/"*) echo "User" ;;
esac
exit 0
STUB
    chmod +x "$WORK_DIR/bin/gh"
}

run_setup() {
    # run_setup <stdin answers> [VAR=value...]: runs scaffold_kanban_setup, prints its output.
    local str_answers="$1"
    shift
    : >"$WORK_DIR/gh.log"
    : >"$WORK_DIR/gh.log.stdin"
    (
        export GH_LOG="$WORK_DIR/gh.log" PATH="$WORK_DIR/bin:$PATH" GITHUB_USERNAME=octo PROJECT_NAME=widget
        export DEFAULT_GITHUB_USERNAME=octo
        local str_kv
        for str_kv in "$@"; do export "${str_kv?}"; done
        # shellcheck source=bin/lib/scaffold_git_remote.sh
        source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"
        printf '%b' "$str_answers" | scaffold_kanban_setup 2>&1
    )
}

expect_log() {
    # $1 = description, $2 = fixed string, $3 = present|absent
    local str_hit="absent"
    grep -qF -- "$2" "$WORK_DIR/gh.log" "$WORK_DIR/gh.log.stdin" && str_hit="present"
    if [ "$str_hit" != "$3" ]; then
        print_status "error" "$1: '$2' is $str_hit in the gh calls (expected $3)"
        int_failures=$((int_failures + 1))
    fi
}

expect_out() {
    # $1 = description, $2 = output, $3 = fixed string it must contain
    if ! grep -qF -- "$3" <<<"$2"; then
        print_status "error" "$1: output never said '$3': ${2: -300}"
        int_failures=$((int_failures + 1))
    fi
}

test_house_labels_are_created_idempotently() {
    local str_label str_out
    str_out="$(run_setup 'n\n')"
    for str_label in type:task type:research type:grilling hitl afk oracle:strong oracle:weak do-not-merge; do
        expect_log "house labels" "label create $str_label --repo octo/widget" present
    done
    expect_log "house labels" "--force" present
    expect_out "labels" "$str_out" "House labels created on octo/widget"
}

test_declining_makes_no_board() {
    local str_out
    str_out="$(run_setup 'n\n')"
    expect_log "declined" "project create" absent
    expect_out "declined" "$str_out" "Skipped the kanban board"
}

test_default_creates_the_full_board() {
    local str_out str_field
    str_out="$(run_setup '\n\n')"
    expect_log "board" "project create --owner octo --title widget kanban" present
    expect_log "board" "project edit 7 --owner octo --visibility PUBLIC" present
    expect_log "board" "project link 7 --owner octo --repo octo/widget" present
    for str_field in Priority Size Estimate "Start date" "Target date" Points; do
        expect_log "board fields" "project field-create 7 --owner octo --name $str_field" present
    done
    expect_log "board status" '"name":"Backlog"' present
    expect_log "board status" '"name":"In progress"' present
    expect_log "board status" '"name":"In review"' present
    expect_log "board status" '"name":"Done"' present
    expect_out "board" "$str_out" "No public API for views or built-in workflows"
    expect_out "board" "$str_out" "https://github.com/users/octo/projects/7/workflows"
}

test_visibility_follows_the_answer_and_the_repo() {
    run_setup '\n3\n' >/dev/null
    expect_log "visibility 3" "--visibility PRIVATE" present
    run_setup '\n2\n' GH_REPO_PRIVATE=true >/dev/null
    expect_log "visibility 2 beats a private repo" "--visibility PUBLIC" present
    run_setup '\n\n' GH_REPO_PRIVATE=true >/dev/null
    expect_log "default follows a private repo" "--visibility PRIVATE" present
}

test_an_existing_board_is_skipped_not_duplicated() {
    local str_out
    str_out="$(run_setup '\n' 'GH_PROJECTS={"projects":[{"title":"widget kanban","number":4}]}')"
    expect_log "existing board" "project create" absent
    expect_out "existing board" "$str_out" "already exists (#4)"
}

test_an_ambiguous_board_is_never_guessed() {
    local str_out
    str_out="$(run_setup '\n' 'GH_PROJECTS={"projects":[{"title":"widget kanban","number":4},{"title":"widget kanban","number":9}]}')"
    expect_log "ambiguous boards" "project create" absent
    expect_out "ambiguous boards" "$str_out" "More than one 'widget kanban' project exists"
}

test_a_missing_scope_prints_the_fix_and_carries_on() {
    local str_out
    str_out="$(run_setup '\n\n' GH_SCOPE_FAIL=1)" || {
        print_status "error" "a failed board must not fail the scaffold"
        int_failures=$((int_failures + 1))
    }
    expect_out "missing scope" "$str_out" "gh auth refresh -s project"
    expect_log "missing scope" "project link" absent
}

main() {
    make_stub
    # Every case must hit the stub: a real `gh` here would try the real GitHub API.
    [ "$(PATH="$WORK_DIR/bin:$PATH" command -v gh)" = "$WORK_DIR/bin/gh" ] || exit 2
    test_house_labels_are_created_idempotently
    test_declining_makes_no_board
    test_default_creates_the_full_board
    test_visibility_follows_the_answer_and_the_repo
    test_an_existing_board_is_skipped_not_duplicated
    test_an_ambiguous_board_is_never_guessed
    test_a_missing_scope_prints_the_fix_and_carries_on
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures failure(s)"
        exit 1
    fi
    print_status "success" "all scaffold-kanban checks passed"
}

main "$@"

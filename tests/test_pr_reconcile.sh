#!/bin/bash

set -uo pipefail
while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e GIT_)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/templates/python-common/bin/pr_reconcile.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

cat >"$WORK_DIR/gh" <<'STUB'
#!/bin/bash
echo "gh $*" >>"$STUB_LOG"
case "$*" in
*"issue view"*) [[ "$*" == *"--repo o/r"* ]] && echo OPEN || exit 1 ;;
*"--json merged"*) echo 'Unknown JSON field: "merged"' >&2; exit 1 ;;
*"--json state --jq .state"*)
    [ "${STUB_STATE_FAIL:-}" = 1 ] && { echo "boom" >&2; exit 1; }
    echo MERGED ;;
*"--json closingIssuesReferences"*)
    [[ "$*" == *nameWithOwner* ]] && { echo "null#65"; exit 0; }
    echo "o/r#65" ;;
*"--json headRefName"*) echo feat-x ;;
*"pr list"*)
	[ "${STUB_LIST_FAIL:-}" = 1 ] && { echo "boom" >&2; exit 1; }
	[ "${STUB_LIST_EMPTY:-}" = 1 ] || echo 7
	;;
*"--json isCrossRepository"*) echo false ;;
*"--json headRefOid"*) echo aaa111 ;;
*"git/refs/heads/feat-x"*) [[ "$*" == *DELETE* ]] || echo aaa111 ;;
esac
exit 0
STUB
cat >"$WORK_DIR/git" <<'STUB'
#!/bin/bash
echo "git $*" >>"$STUB_LOG"
exit 0
STUB
chmod +x "$WORK_DIR/gh" "$WORK_DIR/git"

run_reconcile() {
	: >"$WORK_DIR/log"
	PATH="$WORK_DIR:$PATH" STUB_LOG="$WORK_DIR/log" GH_TOKEN=t GH_REPO=o/r \
		EVENT_PR="${STUB_EVENT_PR-7}" STUB_STATE_FAIL="${1:-}" bash "$SCRIPT" >>"$WORK_DIR/log" 2>&1
	echo "rc=$?" >>"$WORK_DIR/log"
	cat "$WORK_DIR/log"
}

assert_has() {
	if grep -q -- "$2" <<<"$3"; then
		echo "ok: $1"
	else
		echo "FAIL ($1): $(tr '\n' '|' <<<"$3")"
		int_failures=$((int_failures + 1))
	fi
}

assert_lacks() {
	if grep -q -- "$2" <<<"$3"; then
		echo "FAIL ($1): $(tr '\n' '|' <<<"$3")"
		int_failures=$((int_failures + 1))
	else
		echo "ok: $1"
	fi
}

test_merged_pr_closes_its_issue_in_the_owner_name_repo() {
	assert_has "a merged PR closes o/r#65" "gh issue close 65 --repo o/r" "$(run_reconcile)"
}

test_branch_delete_carries_an_expected_sha_lease() {
	assert_has "the delete is a leased push" \
		"git push --force-with-lease=refs/heads/feat-x:aaa111" "$(run_reconcile)"
}

test_branch_delete_never_uses_the_unconditional_rest_delete() {
	assert_lacks "no unconditional DELETE" "-X DELETE" "$(run_reconcile)"
}

test_unreadable_state_is_annotated_in_the_run_summary() {
	assert_has "a failed state lookup is a ::warning::" "::warning::PR #7" "$(run_reconcile 1)"
}

test_unreadable_state_leaves_the_janitor_green() {
	assert_has "a janitor reports and exits 0" "rc=0" "$(run_reconcile 1)"
}

test_failed_sweep_discovery_is_not_reported_as_nothing_to_do() {
	assert_has "a failed pr list is announced" "::warning::could not list merged PRs" \
		"$(STUB_EVENT_PR="" STUB_LIST_FAIL=1 run_reconcile)"
}

test_failed_sweep_discovery_leaves_the_janitor_green() {
	assert_has "a failed pr list exits 0" "rc=0" \
		"$(STUB_EVENT_PR="" STUB_LIST_FAIL=1 run_reconcile)"
}

test_an_empty_sweep_exits_0() {
	assert_has "an empty sweep exits 0" "rc=0" "$(STUB_EVENT_PR="" STUB_LIST_EMPTY=1 run_reconcile)"
}

test_an_empty_sweep_is_not_reported_as_a_failure() {
	assert_lacks "an empty sweep raises no warning" "::warning::" \
		"$(STUB_EVENT_PR="" STUB_LIST_EMPTY=1 run_reconcile)"
}

test_merged_pr_closes_its_issue_in_the_owner_name_repo
test_branch_delete_carries_an_expected_sha_lease
test_branch_delete_never_uses_the_unconditional_rest_delete
test_unreadable_state_is_annotated_in_the_run_summary
test_unreadable_state_leaves_the_janitor_green
test_failed_sweep_discovery_is_not_reported_as_nothing_to_do
test_failed_sweep_discovery_leaves_the_janitor_green
test_an_empty_sweep_exits_0
test_an_empty_sweep_is_not_reported_as_a_failure

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

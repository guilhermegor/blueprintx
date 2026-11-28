#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES="$REPO_ROOT/templates/python-common/bin/enable_repo_rules.sh"
WORKFLOWS=(
	"$REPO_ROOT/.github/workflows/review_threads.yml"
	"$REPO_ROOT/templates/python-common/.github/workflows/review-threads.yml"
)
int_failures=0

check() {
	if "${@:2}"; then
		echo "ok: $1"
	else
		echo "FAIL: $1"
		int_failures=$((int_failures + 1))
	fi
}

each_workflow() {
	local str_wf
	for str_wf in "${WORKFLOWS[@]}"; do
		"$@" "$str_wf" || return 1
	done
}

mint_is_gated() { grep -A2 'id: app$' "$1" | grep -qF "env.REVIEW_APP_CONFIGURED == 'true' && needs.review-gate-runner.outputs.head_sha != ''"; }
mint_is_sha_pinned() { grep -qE 'uses: actions/create-github-app-token@[0-9a-f]{40} # v' "$1"; }
mint_scopes_are_minimal() {
	grep -q 'permission-checks: write' "$1" && [ "$(grep -c 'permission-' "$1")" -eq 1 ]
}
skip_notice_logged() { grep -q '::notice::REVIEW_APP_CLIENT_ID' "$1"; }
gate_keeps_github_token() {
	awk '/id: gate$/{f=1} f&&/GH_TOKEN:/{print; exit}' "$1" | grep -qF 'secrets.GITHUB_TOKEN'
}
publish_is_gated() {
	grep -A1 'name: Publish the check run' "$1" | grep -qF "env.REVIEW_APP_CONFIGURED == 'true'"
}
publish_needs_mint() {
	grep -A1 'name: Publish the check run' "$1" | grep -qF "steps.app.outcome == 'success'"
}
publish_uses_resolved_head() {
	awk '/name: Publish the check run/{f=1} f' "$1" | grep -qF 'STR_HEAD: ${{ needs.review-gate-runner.outputs.head_sha }}' &&
		awk '/name: Post the required/{f=1} /name: Fail this job/{f=0} f' "$1" | grep -qF 'EVALUATED_HEAD: ${{ steps.head.outputs.sha }}'
}
gate_never_reruns_its_own_group() { ! grep -q 'rerun_stale_gate_runs' "$1"; }
post_needs_a_head() {
	awk '/name: Post the required/{f=1} f' "$1" | grep -m1 'if:' | grep -qF "steps.head.outputs.sha != ''"
}
runs_are_serialized_per_pr() {
	awk '/^  publish-app-check:/{f=1} f' "$1" | grep -A2 '^    concurrency:' |
		grep -qF 'group: review-app-check-${{ github.event.pull_request.number || github.event.issue.number }}-${{ needs.review-gate-runner.outputs.head_sha }}' &&
		awk '/^  publish-app-check:/{f=1} f' "$1" | grep -A3 '^    concurrency:' | grep -qF 'cancel-in-progress: false'
}
gate_job_holds_no_app_token() { ! awk '/^  publish-app-check:/{f=1} !f' "$1" | grep -qE 'create-github-app-token|REVIEW_APP_'; }
only_a_passing_gate_publishes_success() {
	grep -qF 'if [ "$GATE_OUTCOME" = success ] && [ "$HEAD_STABLE" = true ]; then str_conclusion=success; fi' "$1" &&
		! grep -qF 'cancelled) str_conclusion' "$1"
}
head_resolved_before_the_guard() {
	grep -q 'name: Gate files unchanged' "$1" || return 0
	[ "$(grep -n 'id: head$' "$1" | cut -d: -f1)" -lt "$(grep -n 'name: Gate files unchanged' "$1" | cut -d: -f1)" ]
}
publish_checks_the_head_did_not_move() {
	grep -qF 'head_stable: ${{ steps.stable.outputs.stable }}' "$1" &&
		awk '/id: stable$/{f=1} /name: Post the required/{f=0} f' "$1" | grep -qF "[ \"\$str_now\" = \"\$STR_HEAD\" ]"
}
publish_job_runs_no_pr_code() {
	awk '/^  publish-app-check:/{f=1} f' "$1" | grep -qE 'actions/checkout|setup-python|python3? |bin/' && return 1
	awk '/^  publish-app-check:/{f=1} f' "$1" | grep -qF 'needs: review-gate-runner'
}
publish_uses_app_token() { grep -qF 'GH_TOKEN: ${{ steps.app.outputs.token }}' "$1"; }

check "mint step runs only when the App secrets are set" each_workflow mint_is_gated
check "mint action is pinned to a full commit SHA" each_workflow mint_is_sha_pinned
check "minted token asks for checks write only" \
	each_workflow mint_scopes_are_minimal
check "one ::notice:: says the App path was skipped" each_workflow skip_notice_logged
check "the gate step still runs on GITHUB_TOKEN" each_workflow gate_keeps_github_token
check "check publishing runs only when the App is configured" each_workflow publish_is_gated
check "check publishing is skipped when minting failed" each_workflow publish_needs_mint
check "posting and publishing share the head resolved before the gate" \
	each_workflow publish_uses_resolved_head
check "no step re-runs this workflow, which would cancel the run in its own concurrency group" \
	each_workflow gate_never_reruns_its_own_group
check "the check-run POST is skipped when no head was resolved" each_workflow post_needs_a_head
check "the publisher has its own per-PR, per-head group with cancel-in-progress: false" each_workflow runs_are_serialized_per_pr
check "the job that runs PR code holds no App token" each_workflow gate_job_holds_no_app_token
check "the head SHA is resolved before the protected-file guard" each_workflow head_resolved_before_the_guard
check "success needs the head to be unchanged since the gate started" each_workflow publish_checks_the_head_did_not_move
check "only a passing gate publishes success" each_workflow only_a_passing_gate_publishes_success
publish_job_fails_on_empty_head() {
	awk '/^  publish-app-check:/{f=1} f' "$1" | grep -A1 'name: Fail when the gate job produced no head SHA' |
		grep -qF "needs.review-gate-runner.outputs.head_sha == ''"
}
check "the publish job fails loud when no head SHA came from the gate job" each_workflow publish_job_fails_on_empty_head
check "the publish job checks out and runs no PR code" each_workflow publish_job_runs_no_pr_code
check "check publishing uses the App token" each_workflow publish_uses_app_token

dry() { env -u REVIEW_APP_INTEGRATION_ID "$@" bash "$RULES" dry_run; }
unpinned_by_default() { dry | grep -qF '"context":"Review threads answered"}' && ! dry | grep -q integration_id; }
pinned_when_set() { dry REVIEW_APP_INTEGRATION_ID=12345 | grep -q '"context":"Review threads answered","integration_id":12345'; }
rejects_non_numeric() {
	local str_out int_rc
	str_out="$(REVIEW_APP_INTEGRATION_ID='1;x' bash "$RULES" dry_run 2>&1)"
	int_rc=$?
	[ "$int_rc" -eq 2 ] && grep -qF "must be the App's numeric id" <<<"$str_out"
}

pin_warning_only_when_pinned() {
	local str_dir str_out
	str_dir="$(mktemp -d)"
	cp -r "$(dirname "$RULES")"/. "$str_dir"/
	printf 'Classify and gate this PR\n' >"$str_dir/required-checks.txt"
	printf '#!/bin/sh\nexit 1\n' >"$str_dir/gh"
	chmod +x "$str_dir/gh"
	str_out="$(PATH="$str_dir:$PATH" REVIEW_APP_INTEGRATION_ID=12345 timeout 30 bash "$str_dir/enable_repo_rules.sh" 2>&1 </dev/null || true)"
	rm -rf "$str_dir"
	! grep -qF 'is pinned to App' <<<"$str_out"
}
warns_when_pinned() {
	local str_dir str_out
	str_dir="$(mktemp -d)"
	cp -r "$(dirname "$RULES")"/. "$str_dir"/
	printf 'Review threads answered\n' >"$str_dir/required-checks.txt"
	printf '#!/bin/sh\nexit 1\n' >"$str_dir/gh"
	chmod +x "$str_dir/gh"
	str_out="$(PATH="$str_dir:$PATH" REVIEW_APP_INTEGRATION_ID=12345 timeout 30 bash "$str_dir/enable_repo_rules.sh" 2>&1 </dev/null || true)"
	rm -rf "$str_dir"
	grep -qF 'is pinned to App' <<<"$str_out"
}

check "no pin warning when the review check is not in required-checks" pin_warning_only_when_pinned
check "the pin warning appears when the review check is pinned" warns_when_pinned
check "dry_run prints no integration_id when the flag is unset" unpinned_by_default
check "dry_run pins the review check when the id is set" pinned_when_set
leading_zero_refused() {
	local str_out int_rc
	str_out="$(REVIEW_APP_INTEGRATION_ID=0123 bash "$RULES" dry_run 2>&1)"
	int_rc=$?
	[ "$int_rc" -eq 2 ] && grep -qF "must be the App's numeric id" <<<"$str_out"
}
check "a leading-zero integration id is refused" leading_zero_refused
check "a non-numeric integration id is refused" rejects_non_numeric

gate_holds_no_actions_write() { ! grep -qE '^ +actions: write$' "$1"; }
check "no job holds actions: write now that nothing re-runs a workflow" each_workflow gate_holds_no_actions_write

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

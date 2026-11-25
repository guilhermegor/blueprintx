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

mint_is_gated() { grep -A2 'id: app$' "$1" | grep -qF "env.REVIEW_APP_CONFIGURED == 'true' && steps.head.outcome == 'success'"; }
mint_after_gate() { [ "$(grep -n 'id: gate$' "$1" | cut -d: -f1)" -lt "$(grep -n 'id: app$' "$1" | cut -d: -f1)" ]; }
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
	awk '/name: Publish the check run/{f=1} f' "$1" | grep -qF 'STR_HEAD: ${{ steps.head.outputs.sha }}' &&
		awk '/name: Clear stale/{f=1} /name: Mint/{f=0} f' "$1" | grep -qF 'STR_HEAD: ${{ steps.head.outputs.sha }}'
}
publish_uses_app_token() { grep -qF 'GH_TOKEN: ${{ steps.app.outputs.token }}' "$1"; }

check "mint step runs only when the App secrets are set" each_workflow mint_is_gated
check "the App token is minted after the gate step" each_workflow mint_after_gate
check "mint action is pinned to a full commit SHA" each_workflow mint_is_sha_pinned
check "minted token asks for checks write only" \
	each_workflow mint_scopes_are_minimal
check "one ::notice:: says the App path was skipped" each_workflow skip_notice_logged
check "the gate step still runs on GITHUB_TOKEN" each_workflow gate_keeps_github_token
check "check publishing runs only when the App is configured" each_workflow publish_is_gated
check "check publishing is skipped when minting failed" each_workflow publish_needs_mint
check "stale-run clearing and publishing share the head resolved before the gate" \
	each_workflow publish_uses_resolved_head
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

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

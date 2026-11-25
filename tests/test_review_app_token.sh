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

mint_is_gated() { grep -A2 'id: app$' "$1" | grep -qF "if: env.REVIEW_APP_CONFIGURED == 'true'"; }
mint_is_sha_pinned() { grep -qE 'uses: actions/create-github-app-token@[0-9a-f]{40} # v' "$1"; }
mint_scopes_are_minimal() {
	grep -q 'permission-checks: write' "$1" && grep -q 'permission-pull-requests: read' "$1" &&
		grep -q 'permission-contents: read' "$1" && ! grep -qE 'permission-(contents|pull-requests): write' "$1"
}
skip_notice_logged() { grep -q '::notice::REVIEW_APP_CLIENT_ID' "$1"; }
gate_keeps_github_token() {
	awk '/id: gate$/{f=1} f&&/GH_TOKEN:/{print; exit}' "$1" | grep -qF 'secrets.GITHUB_TOKEN'
}
publish_is_gated() {
	grep -A1 'name: Publish the check run' "$1" | grep -qF "env.REVIEW_APP_CONFIGURED == 'true'"
}
publish_uses_app_token() { grep -qF 'GH_TOKEN: ${{ steps.app.outputs.token }}' "$1"; }

check "mint step runs only when the App secrets are set" each_workflow mint_is_gated
check "mint action is pinned to a full commit SHA" each_workflow mint_is_sha_pinned
check "minted token asks for checks write, pull-requests read, contents read only" \
	each_workflow mint_scopes_are_minimal
check "one ::notice:: says the App path was skipped" each_workflow skip_notice_logged
check "the gate step still runs on GITHUB_TOKEN" each_workflow gate_keeps_github_token
check "check publishing runs only when the App is configured" each_workflow publish_is_gated
check "check publishing uses the App token" each_workflow publish_uses_app_token

dry() { env -u REVIEW_APP_INTEGRATION_ID "$@" bash "$RULES" dry_run; }
unpinned_by_default() { ! dry | grep -q integration_id; }
pinned_when_set() { dry REVIEW_APP_INTEGRATION_ID=12345 | grep -q '"context":"Review threads answered","integration_id":12345'; }
rejects_non_numeric() { ! REVIEW_APP_INTEGRATION_ID='1;x' bash "$RULES" dry_run >/dev/null 2>&1; }

check "dry_run prints no integration_id when the flag is unset" unpinned_by_default
check "dry_run pins the review check when the id is set" pinned_when_set
check "a non-numeric integration id is refused" rejects_non_numeric

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

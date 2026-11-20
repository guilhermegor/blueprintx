#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

close_linked_issues() {
	local str_pr="$1"
	local str_link str_issue str_issue_repo str_state

	for str_link in $(gh pr view "$str_pr" --json closingIssuesReferences \
		--jq '.closingIssuesReferences[] | "\(.repository.owner.login)/\(.repository.name)#\(.number)"' \
		2>/dev/null || true); do
		str_issue_repo="${str_link%%#*}"
		str_issue="${str_link##*#}"
		str_state="$(gh issue view "$str_issue" --repo "$str_issue_repo" --json state \
			--jq .state 2>/dev/null || echo "")"
		if [[ "$str_state" == "OPEN" ]]; then
			print_status "info" "PR #$str_pr -> closing issue $str_issue_repo#$str_issue"
			gh issue close "$str_issue" --repo "$str_issue_repo" --reason completed \
				--comment "Closed by #$str_pr (reconciled: a bot-performed merge does not close linked issues)." ||
				print_status "warning" "could not close issue $str_issue_repo#$str_issue"
		fi
	done
}

delete_head_branch() {
	local str_pr="$1"
	local str_ref str_is_fork str_merged_sha str_live_sha

	str_ref="$(gh pr view "$str_pr" --json headRefName --jq .headRefName 2>/dev/null || echo "")"
	str_is_fork="$(gh pr view "$str_pr" --json isCrossRepository --jq .isCrossRepository 2>/dev/null || echo "true")"
	str_merged_sha="$(gh pr view "$str_pr" --json headRefOid --jq .headRefOid 2>/dev/null || echo "")"

	[[ -n "$str_ref" && "$str_is_fork" == "false" && -n "$str_merged_sha" ]] || return 0

	str_live_sha="$(gh api "repos/$GH_REPO/git/refs/heads/$str_ref" --jq .object.sha 2>/dev/null || echo "")"

	if [[ -z "$str_live_sha" ]]; then
		return 0
	fi

	if [[ "$str_live_sha" != "$str_merged_sha" ]]; then
		print_status "warning" \
			"PR #$str_pr -> branch $str_ref moved since the merge ($str_live_sha), leaving it"
		return 0
	fi

	if push_delete_with_lease "$str_ref" "$str_merged_sha"; then
		print_status "success" "PR #$str_pr -> deleted branch $str_ref"
	else
		print_status "warning" "PR #$str_pr -> branch $str_ref moved or could not be deleted, leaving it"
	fi
}

push_delete_with_lease() {
	local str_ref="$1"
	local str_sha="$2"
	local str_auth

	str_auth="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
	GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraheader \
		GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $str_auth" \
		git push --force-with-lease="refs/heads/$str_ref:$str_sha" \
		"https://github.com/$GH_REPO.git" ":refs/heads/$str_ref" >/dev/null 2>&1
}

warn_annotated() {
	local str_message="$1"

	echo "::warning::$str_message"
	print_status "warning" "$str_message"
}

reconcile_pr() {
	local str_pr="$1"
	local str_state

	if ! str_state="$(gh pr view "$str_pr" --json state --jq .state)"; then
		warn_annotated "PR #$str_pr -> could not read its state, leaving it for the next sweep"
		return 0
	fi
	[[ "$str_state" == "MERGED" ]] || return 0

	close_linked_issues "$str_pr"
	delete_head_branch "$str_pr"
}

main() {
	local str_pr
	local str_prs

	if [[ -n "${EVENT_PR:-}" ]]; then
		reconcile_pr "$EVENT_PR"
		return
	fi

	if ! str_prs="$(gh pr list --state merged --limit "${SWEEP_LIMIT:-30}" --json number --jq '.[].number')"; then
		warn_annotated "could not list merged PRs; nothing was reconciled this run"
		return 0
	fi
	for str_pr in $str_prs; do
		reconcile_pr "$str_pr"
	done
}

main "$@"

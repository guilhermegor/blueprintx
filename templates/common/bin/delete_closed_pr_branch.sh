#!/usr/bin/env bash

set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/check_pr_policy.sh"

note() {
	echo "$1"
	[[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && echo "$1" >>"$GITHUB_STEP_SUMMARY"
	return 0
}

skip_reason() {
	local str_head="$1" str_base="$2"
	[[ "$str_head" == "$str_base" ]] && { echo "it is the PR's base branch"; return 0; }
	is_short_lived_branch "$str_head" && return 0
	echo "its name is not a short-lived <type>/<N>-<slug> branch"
}

is_protected() {
	local str_out
	str_out=$(gh api "repos/${GH_REPO}/branches/${BRANCH}" --jq .protected 2>&1) || {
		[[ "$str_out" == *"HTTP 404"* ]] && return 1
		echo "protection unreadable: ${str_out}"
		return 0
	}
	[[ "$str_out" == "false" ]] && return 1
	echo "branch is protected"
}

delete_ref() {
	local str_url="repos/${GH_REPO}/git/refs/heads/${BRANCH}" str_tip str_out
	if ! str_tip=$(gh api "$str_url" --jq .object.sha 2>&1); then
		[[ "$str_tip" == *"HTTP 404"* ]] && { note "Branch \`${BRANCH}\` of PR #${PR} is already deleted; nothing to do."; return 0; }
		echo "$str_tip" >&2
		return 1
	fi
	if [[ "$str_tip" != "$HEAD_SHA" ]]; then
		note "Kept \`${BRANCH}\`: its tip \`${str_tip}\` is not the PR #${PR} head \`${HEAD_SHA}\`."
		return 0
	fi
	if str_out=$(gh api -X DELETE "$str_url" 2>&1); then
		note "Deleted \`${BRANCH}\` at \`${str_tip}\` (PR #${PR} closed without merge)."
		note "Restore: PR #${PR} page, 'Restore branch', or \`git push origin ${str_tip}:refs/heads/${BRANCH}\`."
		return 0
	fi
	if [[ "$str_out" == *"HTTP 404"* || "$str_out" == *"HTTP 422"* ]]; then
		note "Branch \`${BRANCH}\` was already gone or refused deletion: ${str_out}"
		return 0
	fi
	echo "$str_out" >&2
	return 1
}

main() {
	local str_why
	str_why=$(skip_reason "$BRANCH" "$BASE_REF")
	[[ -n "$str_why" ]] && { note "Kept \`${BRANCH}\` of PR #${PR}: ${str_why}."; return 0; }
	str_why=$(is_protected)
	[[ -n "$str_why" ]] && { note "Kept \`${BRANCH}\` of PR #${PR}: ${str_why}."; return 0; }
	delete_ref
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi

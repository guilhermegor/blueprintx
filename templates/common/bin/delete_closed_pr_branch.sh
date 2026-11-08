#!/usr/bin/env bash

set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/check_pr_policy.sh"

note() {
	echo "$1"
	[[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && echo "$1" >>"$GITHUB_STEP_SUMMARY"
	return 0
}

skip_reason() {
	local str_head="$1" str_base="$2" str_default="$3"
	[[ -z "$str_default" || -z "$str_base" ]] && { echo "the default or base branch is unknown"; return 0; }
	[[ "$str_head" == "$str_default" ]] && { echo "it is the default branch"; return 0; }
	[[ "$str_head" == "$str_base" ]] && { echo "it is the PR's base branch"; return 0; }
	[[ "$str_head" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo "its name has characters that cannot be sent safely in an API path"; return 0; }
	is_short_lived_branch "$str_head" && return 0
	echo "its name is not a short-lived <type>/<N>-<slug> branch"
}

api() {
	local str_errfile
	str_errfile=$(mktemp)
	STR_OUT=$(gh api "$@" 2>"$str_errfile")
	local int_rc=$?
	STR_ERR=$(<"$str_errfile")
	rm -f "$str_errfile"
	return "$int_rc"
}

is_protected() {
	api "repos/${GH_REPO}/branches/${BRANCH}" --jq .protected || {
		[[ "${STR_ERR}${STR_OUT}" == *"HTTP 404"* ]] && return 1
		echo "protection unreadable: ${STR_ERR}"
		return 0
	}
	[[ "$STR_OUT" == "false" ]] && return 1
	echo "branch is protected"
}

used_by_open_pr() {
	local str_query str_role
	for str_role in base head; do
		str_query="state=open&${str_role}=${BRANCH}"
		[[ "$str_role" == "head" ]] && str_query="state=open&head=${GH_REPO%%/*}:${BRANCH}"
		api "repos/${GH_REPO}/pulls?${str_query}" --jq length || {
			echo "open PRs using it as ${str_role} unreadable: ${STR_ERR}"
			return 0
		}
		[[ "$STR_OUT" =~ ^[0-9]+$ ]] || { echo "open PRs using it as ${str_role} unreadable: unexpected reply"; return 0; }
		((STR_OUT > 0)) && { echo "${STR_OUT} other open PR(s) use it as their ${str_role} (deleting it would close them)"; return 0; }
	done
	return 1
}

delete_ref() {
	local str_url="repos/${GH_REPO}/git/refs/heads/${BRANCH}" str_tip
	if ! api "repos/${GH_REPO}/git/ref/heads/${BRANCH}" --jq .object.sha; then
		[[ "${STR_ERR}${STR_OUT}" == *"HTTP 404"* ]] && { note "Branch \`${BRANCH}\` of PR #${PR} is already deleted; nothing to do."; return 0; }
		echo "$STR_ERR" >&2
		return 1
	fi
	str_tip="$STR_OUT"
	if [[ "$str_tip" != "$HEAD_SHA" ]]; then
		note "Kept \`${BRANCH}\`: its tip \`${str_tip}\` is not the PR #${PR} head \`${HEAD_SHA}\`."
		return 0
	fi
	if api -X DELETE "$str_url"; then
		note "Deleted \`${BRANCH}\` at \`${str_tip}\` (PR #${PR} closed without merge)."
		note "Restore: PR #${PR} page, 'Restore branch' (needed before the PR can be reopened), or from a clone holding the commit \`git push origin ${str_tip}:refs/heads/${BRANCH}\`."
		return 0
	fi
	local str_all="${STR_ERR}${STR_OUT}"
	if [[ "$str_all" == *"HTTP 404"* || "$str_all" == *"Reference does not exist"* ]]; then
		note "Branch \`${BRANCH}\` was already gone: ${STR_ERR}"
		return 0
	fi
	if [[ "$str_all" == *"Repository rule violations"* ]]; then
		note "Kept \`${BRANCH}\`: a repository ruleset refused the deletion: ${STR_ERR}"
		return 0
	fi
	echo "$STR_ERR" >&2
	return 1
}

main() {
	local str_why
	str_why=$(skip_reason "$BRANCH" "$BASE_REF" "$DEFAULT_BRANCH")
	[[ -n "$str_why" ]] && { note "Kept \`${BRANCH}\` of PR #${PR}: ${str_why}."; return 0; }
	str_why=$(is_protected)
	[[ -n "$str_why" ]] && { note "Kept \`${BRANCH}\` of PR #${PR}: ${str_why}."; return 0; }
	str_why=$(used_by_open_pr)
	[[ -n "$str_why" ]] && { note "Kept \`${BRANCH}\` of PR #${PR}: ${str_why}."; return 0; }
	delete_ref
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi

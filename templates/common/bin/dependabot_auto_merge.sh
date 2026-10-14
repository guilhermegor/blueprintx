#!/usr/bin/env bash

set -uo pipefail

readonly DEPENDABOT_LOGIN="dependabot[bot]"

classify_update() {
	local str_json="${1:-}"
	if printf '%s' "$str_json" | jq -e 'type == "array" and length > 0 and all(.[]; .updateType == "version-update:semver-patch" or .updateType == "version-update:semver-minor")' >/dev/null 2>&1; then
		echo minor
	else
		echo major
	fi
}

is_pure_dependabot() {
	local str_pr="$1" str_bad
	[[ "$(gh api "repos/$GH_REPO/pulls/$str_pr" --jq .user.login)" == "$DEPENDABOT_LOGIN" ]] || return 1
	str_bad=$(gh api "repos/$GH_REPO/pulls/$str_pr/commits" --paginate \
		--jq "[.[] | select(.author.login != \"$DEPENDABOT_LOGIN\")] | length") || return 1
	[[ -n "$str_bad" ]] && [[ "${str_bad//[0 $'\n']/}" == "" ]]
}

has_review_on_head() {
	local str_pr="$1" str_head="$2" str_n
	str_n=$(gh api "repos/$GH_REPO/pulls/$str_pr/reviews" --paginate --jq \
		"[.[] | select(.commit_id == \"$str_head\" and .user.login != \"$DEPENDABOT_LOGIN\" and (.state == \"APPROVED\" or .state == \"COMMENTED\" or .state == \"CHANGES_REQUESTED\"))] | length") || return 1
	[[ "${str_n//[0 $'\n']/}" == "" ]] && return 1
	return 0
}

decide() {
	local str_pr="$1" str_head="$2" str_json="$3"
	is_pure_dependabot "$str_pr" || { echo skip; return 0; }
	if [[ "$(classify_update "$str_json")" == minor ]]; then
		echo arm
	elif has_review_on_head "$str_pr" "$str_head"; then
		echo arm
	else
		echo wait-review
	fi
}

main() {
	local str_decision
	str_decision=$(decide "$PR" "$HEAD_SHA" "${DEPS_JSON:-}") || return 1
	case "$str_decision" in
	arm) gh pr merge "$PR" --auto --squash --repo "$GH_REPO" ;;
	wait-review) echo "::notice::major update: waiting for a review on $HEAD_SHA; re-run this job after it" ;;
	*) echo "::notice::not a pure Dependabot PR: auto-merge not armed" ;;
	esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main
fi

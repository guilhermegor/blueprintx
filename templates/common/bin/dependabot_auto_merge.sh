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
	[[ "$(gh api "repos/$GH_REPO/pulls/$str_pr" | jq -r .user.login)" == "$DEPENDABOT_LOGIN" ]] || return 1
	str_bad=$(gh api "repos/$GH_REPO/pulls/$str_pr/commits" --paginate |
		jq -s --arg bot "$DEPENDABOT_LOGIN" '[.[][] | select(.author.login != $bot)] | length') || return 1
	[[ "$str_bad" == 0 ]]
}

has_review_on_head() {
	local str_pr="$1" str_head="$2" str_n
	str_n=$(gh api "repos/$GH_REPO/pulls/$str_pr/reviews" --paginate |
		jq -s --arg head "$str_head" --arg bot "$DEPENDABOT_LOGIN" \
			'[.[][] | select(.commit_id == $head and .user.login != $bot and (.author_association | IN("OWNER", "MEMBER", "COLLABORATOR")))] as $r
			| if any($r[]; .state == "CHANGES_REQUESTED") then 0
			  else [$r[] | select(.state | IN("APPROVED", "COMMENTED"))] | length end') || return 1
	[[ "$str_n" =~ ^[0-9]+$ ]] && ((str_n > 0))
}

disarm() {
	gh pr merge "$1" --disable-auto --repo "$GH_REPO" 2>/dev/null || true
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
	arm) gh pr merge "$PR" --auto --squash --match-head-commit "$HEAD_SHA" --repo "$GH_REPO" ;;
	wait-review)
		disarm "$PR"
		echo "::notice::major update: waiting for a review on $HEAD_SHA"
		;;
	*)
		disarm "$PR"
		echo "::notice::not a pure Dependabot PR: auto-merge not armed"
		;;
	esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main
fi

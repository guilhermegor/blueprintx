#!/usr/bin/env bash

set -uo pipefail

EXEMPT_BRANCHES='^(release|dependabot|renovate)/'
CC_TYPES='feat|fix|chore|test|docs|refactor|perf|build|ci|style|revert'

check_branch() {
	local str_branch="$1"
	[[ "$str_branch" =~ $EXEMPT_BRANCHES ]] && return 0
	[[ "$str_branch" =~ ^[a-z]+/[0-9]+(-|$) ]] && return 0
	echo "Branch '$str_branch' carries no issue number (<type>/<N>-<slug>)." >&2
	return 1
}

check_title() {
	local str_title="$1"
	[[ "$str_title" =~ ^($CC_TYPES)(\([^\)]+\))?!?:\ .*[^[:space:]] ]] && return 0
	echo "Title '$str_title' is not a Conventional Commit (type(scope): subject)." >&2
	return 1
}

check_body() {
	local str_body="$1" str_template="$2" str_head int_missing=0
	[[ -f "$str_template" ]] || { echo "Template $str_template not found." >&2; return 2; }
	while IFS= read -r str_head; do
		if ! printf '%s\n' "$str_body" | tr -d '\r' | sed -E 's/[[:space:]]+$//' | grep -ixF -- "$str_head" >/dev/null; then
			echo "PR body is missing the '$str_head' section." >&2
			int_missing=1
		fi
	done < <(tr -d '\r' < "$str_template" | grep -E '^## ' | sed -E 's/[[:space:]]+$//')
	return "$int_missing"
}

check_assignee() {
	local str_assignees="$1"
	[[ "$str_assignees" =~ [^[:space:]] ]] && return 0
	echo "PR has no assignee." >&2
	return 1
}

linear_key_present() {
	local str_text="${1#*/} $2" str_key
	while read -r str_key; do
		[[ "${str_key,,}" =~ ^(utf|sha|iso|pep|es|http|node|py|rfc|md|ipv)$ ]] || return 0
	done < <(grep -oiE '(^|[^[:alnum:]])[a-z][a-z0-9]*-[0-9]+' <<<"$str_text" | sed -E 's/^[^[:alnum:]]//; s/-[0-9]+$//')
	return 1
}

check_linked_issue() {
	local str_branch="$1" str_title="$2" str_tracker="${3:-github}" int_closing="${4:-0}" str_num str_re=
	[[ "$str_branch" =~ ^(dependabot|renovate)/ ]] && return 0
	case "${str_tracker,,}" in
		github)
			((int_closing > 0)) && return 0
			if [[ "$str_branch" =~ ^[a-z]+/([0-9]+)(-|$) ]]; then
				str_num="${BASH_REMATCH[1]}"
				[[ "$(gh issue view "$str_num" --json state --jq .state 2>/dev/null)" == "OPEN" ]] && return 0
			fi
			echo "PR closes no issue and branch '$str_branch' resolves to no open issue." >&2
			return 1
			;;
		linear) linear_key_present "$str_branch" "$str_title" && return 0 ;;
		regex)
			str_re="${TRACKER_REGEX:-}"
			[[ -n "$str_re" ]] || { echo "TRACKER=regex needs TRACKER_REGEX set." >&2; return 2; }
			;;
		*) echo "Unknown TRACKER '$str_tracker' (github|linear|regex)." >&2; return 2 ;;
	esac
	[[ -n "$str_re" && "$str_branch $str_title" =~ $str_re ]] && return 0
	echo "No $str_tracker issue reference in branch or title." >&2
	return 1
}

main() {
	case "${1:-}" in
		branch) check_branch "${BRANCH:-}" ;;
		title) check_title "${TITLE:-}" ;;
		body) check_body "${BODY:-}" "${TEMPLATE:-.github/PULL_REQUEST_TEMPLATE.md}" ;;
		assignee) check_assignee "${ASSIGNEES:-}" ;;
		linked-issue) check_linked_issue "${BRANCH:-}" "${TITLE:-}" "${TRACKER:-github}" "${CLOSING_COUNT:-0}" ;;
		*) echo "usage: check_pr_policy.sh branch|title|body|assignee|linked-issue" >&2; return 2 ;;
	esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi

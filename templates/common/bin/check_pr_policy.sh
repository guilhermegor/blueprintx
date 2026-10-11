#!/usr/bin/env bash
# PR policy checks run by .github/workflows/{branch-has-issue,pr-title-conventional,
# pr-body-template}.yml (blueprintx#604). Untrusted text arrives only through env.
#
# Usage: check_pr_policy.sh branch|title|body
# Env:   BRANCH (head ref), TITLE (PR title), BODY (PR body), TEMPLATE (default
#        .github/PULL_REQUEST_TEMPLATE.md). Exit 0 pass, 1 policy violation, 2 bad usage.
# Sourcing this file defines the functions without running anything (used by the tests).

set -uo pipefail

# Branches no human numbers by hand: version bumps and dependency bots.
EXEMPT_BRANCHES='^(release|dependabot|renovate)/'
CC_TYPES='feat|fix|chore|test|docs|refactor|perf|build|ci|style|revert'

# Passes a `<type>/<N>-<slug>` branch or a trailing `-<N>` one.
check_branch() {
	local str_branch="$1"
	[[ "$str_branch" =~ $EXEMPT_BRANCHES ]] && return 0
	[[ "$str_branch" =~ ^[a-z]+/[0-9]+- || "$str_branch" =~ -[0-9]+$ ]] && return 0
	echo "Branch '$str_branch' carries no issue number (<type>/<N>-<slug>)." >&2
	return 1
}

# Passes a Conventional Commit subject: type(scope)!: description.
check_title() {
	local str_title="$1"
	[[ "$str_title" =~ ^($CC_TYPES)(\([^\)]+\))?!?:\ .+ ]] && return 0
	echo "Title '$str_title' is not a Conventional Commit (type(scope): subject)." >&2
	return 1
}

# Passes when every `## ` heading of the template starts a line of the body.
check_body() {
	local str_body="$1" str_template="$2" str_head int_missing=0
	[[ -f "$str_template" ]] || { echo "Template $str_template not found." >&2; return 2; }
	while IFS= read -r str_head; do
		if ! printf '%s\n' "$str_body" | tr -d '\r' | grep -qiE "^${str_head}[[:space:]]*$"; then
			echo "PR body is missing the '$str_head' section." >&2
			int_missing=1
		fi
	done < <(tr -d '\r' < "$str_template" | grep -E '^## ' | sed -E 's/[[:space:]]+$//')
	return "$int_missing"
}

main() {
	case "${1:-}" in
		branch) check_branch "${BRANCH:-}" ;;
		title) check_title "${TITLE:-}" ;;
		body) check_body "${BODY:-}" "${TEMPLATE:-.github/PULL_REQUEST_TEMPLATE.md}" ;;
		*) echo "usage: check_pr_policy.sh branch|title|body" >&2; return 2 ;;
	esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi

#!/usr/bin/env bash
# Close the issues a merged PR delivered, for when GitHub's own `Closes #N` linking came
# back empty. Called by .github/workflows/close-linked-issues.yml (blueprintx#604).
#
# Inputs (env): BRANCH (PR head ref), BODY (PR body), PR (PR number), GH_REPO, GH_TOKEN.
# Strict by design: a wrong closure is worse than a missed one, so a number is taken only
# from the leading `<type>/<N>-<slug>` branch form and from `Closes|Fixes|Resolves #N`.
# Sourcing this file defines the functions without running anything (used by the tests).

set -uo pipefail

# Branch types of CONTRIBUTING.md; `release` is deliberately absent (a version, not an issue).
BRANCH_TYPES='feat|feature|fix|bugfix|hotfix|docs|refactor|chore|test'
# GitHub's closing keywords, lowercase (the body is lowercased before matching).
KEYWORDS='(close[sd]?|fix(e[sd])?|resolve[sd]?)'

# Prints the issue number named by a `<type>/<N>-<slug>` branch; nothing for anything else.
issue_from_branch() {
	local str_branch="$1" str_num

	str_num=$(printf '%s' "$str_branch" | sed -nE "s#^($BRANCH_TYPES)/([0-9]+)-.*#\2#p")
	# A leading four-digit year (chore/2026-10-cleanup) is a date, not an issue.
	if [[ "$str_num" =~ ^(19|20)[0-9]{2}$ ]]; then
		return 0
	fi
	[[ -n "$str_num" ]] && printf '%s\n' "$str_num"
	return 0
}

# Prints each issue number that follows a closing keyword in a PR body, one per line.
# Skips negated uses ("not fix #12", "won't close #9"); grep -w supplies the word
# boundaries, so `hotfix #5` and `closes #12abc` never match.
issues_from_body() {
	local str_body="$1"

	printf '%s\n' "$str_body" | tr 'A-Z' 'a-z' \
		| sed -E \
			-e "s/(^|[^[:alnum:]_])(not|never|cannot)([[:space:]]+[[:alpha:]]+){0,3}[[:space:]]+$KEYWORDS:?[[:space:]]+#[0-9]+/ /g" \
			-e "s/n['’]t([[:space:]]+[[:alpha:]]+){0,3}[[:space:]]+$KEYWORDS:?[[:space:]]+#[0-9]+/ /g" \
		| { grep -owE "$KEYWORDS:?[[:space:]]+#[0-9]+" || true; } \
		| grep -oE '[0-9]+$'
}

# Prints the de-duplicated issue numbers for a PR; nothing at all for a bot branch,
# whose body quotes upstream release notes (`Fixes #1234` of ANOTHER repository).
resolve_issues() {
	local str_branch="$1" str_body="$2"

	case "$str_branch" in
		dependabot/* | renovate/* | release/*) return 0 ;;
	esac
	{
		issue_from_branch "$str_branch"
		issues_from_body "$str_body"
	} | sed -E 's/^0+//' | grep -vxE '' | sort -un
}

# Closes one open issue. Returns 0 when closed or deliberately skipped, 1 on a real error.
close_issue() {
	local str_num="$1" str_out str_state

	# The issues endpoint also answers for PR numbers; those are skipped.
	if ! str_out=$(gh api "repos/$GH_REPO/issues/$str_num" \
		--jq 'if .pull_request then "pr" else .state end' 2>&1); then
		if [[ "$str_out" == *"404"* || "$str_out" == *"Not Found"* ]]; then
			echo "#$str_num does not exist, skipped"
			return 0
		fi
		echo "::error::could not read #$str_num: $str_out"
		return 1
	fi
	str_state="$str_out"
	if [[ "$str_state" != "open" ]]; then
		echo "#$str_num is $str_state, skipped"
		return 0
	fi
	if ! gh issue close "$str_num" --reason completed --comment "Delivered in #$PR."; then
		echo "::error::could not close #$str_num"
		return 1
	fi
	echo "closed #$str_num"
}

main() {
	local int_failed=0 str_num

	for str_num in $(resolve_issues "$BRANCH" "$BODY"); do
		[[ "$str_num" == "$PR" ]] && continue
		close_issue "$str_num" || int_failed=1
	done
	return "$int_failed"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main
fi

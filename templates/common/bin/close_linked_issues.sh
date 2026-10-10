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
	# A year followed by a month (chore/2026-10-cleanup) is a date; a bare 1999 is an issue.
	if [[ "$str_branch" =~ /(19|20)[0-9]{2}-(0[1-9]|1[0-2])(-|$) ]]; then
		return 0
	fi
	[[ -n "$str_num" ]] && printf '%s\n' "$str_num"
	return 0
}

# Drops what GitHub's own linker ignores: fenced blocks, `>` quote lines, <!-- --> comments
# (across lines) and inline code spans. What is left is the prose that can close an issue.
strip_non_prose() {
	tr -d '\r' | awk '
		/^[[:space:]]*(```|~~~)/ { fence = !fence; next }
		fence { next }
		{
			str_orig = $0
			str_line = $0
			str_out = ""
			while (1) {
				if (int_comment) {
					int_at = index(str_line, "-->")
					if (!int_at) { str_line = ""; break }
					str_line = substr(str_line, int_at + 3)
					int_comment = 0
				}
				int_at = index(str_line, "<!--")
				if (!int_at) break
				str_out = str_out substr(str_line, 1, int_at - 1) " "
				str_line = substr(str_line, int_at + 4)
				int_comment = 1
			}
			str_line = str_out str_line
			if (str_orig ~ /^[[:space:]]*>/) next
			gsub(/`[^`]*`/, " ", str_line)
			print str_line
		}'
}

# Prints each issue number that follows a closing keyword in a PR body, one per line.
# Skips negated uses ("not fully fix #12", "no longer fixes #8", "reverts the change that
# fixes #8", "won't close #9"), even across a line break; grep -w supplies the word
# boundaries, so `hotfix #5` and `closes #12abc` never match.
issues_from_body() {
	local str_body="$1" str_neg='(not|never|cannot|no longer|reverts?|reverted|reverting|without)'

	printf '%s\n' "$str_body" | strip_non_prose | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' \
		| sed -E \
			-e "s/(^|[^[:alnum:]_])$str_neg([[:space:]]+[[:alpha:]]+){0,3}[[:space:]]+$KEYWORDS:?[[:space:]]+#[0-9]+/ /g" \
			-e "s/n('|’)t([[:space:]]+[[:alpha:]]+){0,3}[[:space:]]+$KEYWORDS:?[[:space:]]+#[0-9]+/ /g" \
		| { grep -owE "$KEYWORDS:?[[:space:]]+#[0-9]+" || true; } \
		| { grep -oE '[0-9]+$' || true; }
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
	} | sed -E 's/^0+//' | { grep -vxE '' || true; } | sort -un
}

# Closes one open issue. Returns 0 when closed or deliberately skipped, 1 on a real error.
close_issue() {
	local str_num="$1" str_state str_err path_err

	path_err=$(mktemp)
	# The issues endpoint also answers for PR numbers; those are skipped. stderr is kept apart
	# so a notice on a successful call cannot pollute the state.
	if ! str_state=$(gh api "repos/$GH_REPO/issues/$str_num" \
		--jq 'if .pull_request then "pr" else .state end' 2>"$path_err"); then
		str_err=$(<"$path_err")
		rm -f "$path_err"
		# 404: no such issue. 410: deleted, or Issues disabled on the repo.
		if [[ "$str_err" =~ \(HTTP\ (404|410)\) ]]; then
			echo "#$str_num does not exist (HTTP ${BASH_REMATCH[1]}), skipped"
			return 0
		fi
		echo "::error::could not read #$str_num: $str_err"
		return 1
	fi
	rm -f "$path_err"
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
	local int_failed=0 str_num str_list

	# Captured first: a for-loop over $(...) would drop a broken parser's status.
	if ! str_list=$(resolve_issues "$BRANCH" "$BODY"); then
		echo "::error::could not parse the branch and body for issue numbers"
		return 1
	fi
	for str_num in $str_list; do
		[[ "$str_num" == "$PR" ]] && continue
		close_issue "$str_num" || int_failed=1
	done
	return "$int_failed"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main
fi

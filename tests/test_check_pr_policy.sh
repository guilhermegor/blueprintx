#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=templates/common/bin/check_pr_policy.sh
source "$REPO_ROOT/templates/common/bin/check_pr_policy.sh"
TEMPLATE="$REPO_ROOT/templates/common/.github/PULL_REQUEST_TEMPLATE.md"

int_failures=0

expect() {
	local str_desc="$1" str_want="$2" str_got=pass
	shift 2
	"$@" >/dev/null 2>&1 || str_got=fail
	if [[ "$str_got" == "$str_want" ]]; then
		echo "ok   - $str_desc"
		return 0
	fi
	echo "FAIL - $str_desc: want $str_want, got $str_got"
	int_failures=$((int_failures + 1))
}

expect "typed branch with number" pass check_branch "feat/604-policies"
expect "slugless number" pass check_branch "feat/604"
expect "version suffix is not an issue" fail check_branch "chore/bump-node-20"
expect "trailing number is not an issue" fail check_branch "feat/my-fix-12"
expect "release branch exempt" pass check_branch "release/1.2.0"
expect "bot branch exempt" pass check_branch "dependabot/npm/foo"
expect "branch without number" fail check_branch "feat/policies"
expect "bare main" fail check_branch "main"

expect "plain title" pass check_title "feat: add thing"
expect "scoped breaking title" pass check_title "fix(ci)!: stop leaking"
expect "title without type" fail check_title "Add thing"
expect "title without space" fail check_title "feat:add thing"
expect "unknown type" fail check_title "wip: thing"
expect "empty subject" fail check_title "feat: "
expect "whitespace-only subject" fail check_title "feat:    "

str_full=$(tr -d '\r' < "$TEMPLATE")
expect "template as body" pass check_body "$str_full" "$TEMPLATE"
expect "empty body" fail check_body "" "$TEMPLATE"
expect "body missing a section" fail check_body "${str_full//## Testing/}" "$TEMPLATE"
str_meta=$(mktemp)
printf '## Testing (CI checklist)\n## A.B+C\n' > "$str_meta"
expect "heading with regex metacharacters" pass check_body $'## Testing (CI checklist)  \n## A.B+C' "$str_meta"
expect "metacharacter heading must not match by regex" fail check_body $'## Testing CI checklist\n## AxB+C' "$str_meta"
rm -f "$str_meta"
expect "missing template is an error" fail check_body "$str_full" "/nonexistent"

SCRIPT="$REPO_ROOT/templates/common/bin/check_pr_policy.sh"
expect "script branch mode, env interface" pass env BRANCH="feat/604-x" bash "$SCRIPT" branch
expect "script branch mode rejects" fail env BRANCH="feat/x" bash "$SCRIPT" branch
expect "script title mode, env interface" pass env TITLE="fix: x" bash "$SCRIPT" title
expect "script body mode, env interface" pass env BODY="$str_full" TEMPLATE="$TEMPLATE" bash "$SCRIPT" body
expect "script body mode rejects" fail env BODY="" TEMPLATE="$TEMPLATE" bash "$SCRIPT" body
expect "assignee present" pass check_assignee "octocat"
expect "no assignee" fail check_assignee ""
expect "whitespace-only assignee" fail check_assignee "  "

gh() { [[ "$3" == "604" ]] && echo OPEN || echo CLOSED; }
expect "closing reference passes" pass check_linked_issue "feat/x" "feat: t" github 1
expect "branch number resolving to open issue" pass check_linked_issue "feat/604-x" "feat: t" github 0
expect "branch number with closed issue" fail check_linked_issue "feat/999-x" "feat: t" github 0
expect "no number and no closing reference" fail check_linked_issue "feat/x" "feat: t" github 0
expect "dependabot branch skips linked-issue" pass check_linked_issue "dependabot/npm/foo" "chore: t" github 0
expect "renovate branch skips linked-issue" pass check_linked_issue "renovate/foo" "chore: t" github 0
expect "linear key in branch" pass check_linked_issue "feat/abc-123-x" "feat: t" linear 0
expect "linear key in title" pass check_linked_issue "feat/x" "feat: ABC-123 t" linear 0
expect "linear without key" fail check_linked_issue "feat/x" "feat: t" linear 0
expect "custom regex match" pass env TRACKER_REGEX='JIRA-[0-9]+' bash -c 'source "$0"; check_linked_issue feat/x "feat: JIRA-7 t" regex 0' "$REPO_ROOT/templates/common/bin/check_pr_policy.sh"
expect "custom regex miss" fail env TRACKER_REGEX='JIRA-[0-9]+' bash -c 'source "$0"; check_linked_issue feat/x "feat: t" regex 0' "$REPO_ROOT/templates/common/bin/check_pr_policy.sh"
expect "linear rejects node-20 version bump branch" fail check_linked_issue "chore/bump-node-20" "chore: bump node" linear 0
expect "linear rejects lowercase token in title" fail check_linked_issue "feat/x" "feat: py-3 support" linear 0
expect "linear uppercase key after boundary in title" pass check_linked_issue "feat/x" "feat(ENG-12): t" linear 0
expect "regex mode without TRACKER_REGEX exits 2" fail env -u TRACKER_REGEX bash -c 'source "$0"; check_linked_issue feat/x "feat: t" regex 0' "$REPO_ROOT/templates/common/bin/check_pr_policy.sh"
expect "release branch still needs a linked issue" fail check_linked_issue "release/1.2.0" "chore: release" github 0
expect "linear rejects UTF-8 in title" fail check_linked_issue "feat/x" "fix: handle UTF-8 BOM" linear 0
expect "linear rejects SHA-256 in title" fail check_linked_issue "feat/x" "feat: SHA-256 sums" linear 0
expect "linear rejects node-20-upgrade branch" fail check_linked_issue "chore/node-20-upgrade" "chore: t" linear 0
expect "linear matches uppercase key in branch" pass check_linked_issue "feat/ABC-123-x" "feat: t" linear 0
expect "linear matches username-prefixed branch" pass check_linked_issue "jo.e-2/abc-123-x" "feat: t" linear 0
expect "tracker name is case-insensitive" pass check_linked_issue "feat/abc-123-x" "feat: t" Linear 0
expect "unknown tracker is an error" fail check_linked_issue "feat/x" "feat: t" bogus 0
unset -f gh

expect "script assignee mode passes" pass env ASSIGNEES="octocat" bash "$REPO_ROOT/templates/common/bin/check_pr_policy.sh" assignee
expect "script assignee mode rejects" fail env ASSIGNEES="" bash "$REPO_ROOT/templates/common/bin/check_pr_policy.sh" assignee
expect "script linked-issue mode passes" pass env BRANCH="feat/x" TITLE="feat: t" CLOSING_COUNT=2 bash "$REPO_ROOT/templates/common/bin/check_pr_policy.sh" linked-issue
expect "script linked-issue mode rejects" fail env BRANCH="feat/x" TITLE="feat: t" CLOSING_COUNT=0 bash "$REPO_ROOT/templates/common/bin/check_pr_policy.sh" linked-issue

int_usage=0
bash "$SCRIPT" bogus >/dev/null 2>&1 || int_usage=$?
expect "usage path exits 2" pass test "$int_usage" -eq 2

if ((int_failures > 0)); then
	echo "$int_failures failure(s)"
	exit 1
fi

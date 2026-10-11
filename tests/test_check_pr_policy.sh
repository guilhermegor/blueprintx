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
int_usage=0
bash "$SCRIPT" bogus >/dev/null 2>&1 || int_usage=$?
expect "usage path exits 2" pass test "$int_usage" -eq 2

if ((int_failures > 0)); then
	echo "$int_failures failure(s)"
	exit 1
fi

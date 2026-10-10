#!/usr/bin/env bash
# Table-driven tests for templates/common/bin/close_linked_issues.sh (blueprintx#604).
#
# A wrong closure is worse than a missed one, so every row below is either a case that must
# close exactly the named issues or a should-fail witness: a case that once misfired (or that
# the PR #675 review showed would) and must close NOTHING. The last block drives the real
# script against a stub `gh` to pin the error handling.
#
# Usage: bash tests/test_close_linked_issues.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/templates/common/bin/close_linked_issues.sh"
# shellcheck source=templates/common/bin/close_linked_issues.sh
source "$SCRIPT"

int_failures=0

# expect <description> <branch> <body> <expected numbers, space separated; empty = none>
expect() {
	local str_desc="$1" str_branch="$2" str_body="$3" str_want="$4" str_got
	str_got=$(resolve_issues "$str_branch" "$str_body" | tr '\n' ' ' | sed 's/ $//')
	if [[ "$str_got" == "$str_want" ]]; then
		echo "ok   - $str_desc"
		return 0
	fi
	echo "FAIL - $str_desc: want '[$str_want]', got '[$str_got]'"
	int_failures=$((int_failures + 1))
}

# Positives.
expect "leading number" "feat/12-add-thing-3" "" "12"
expect "feature/ and bugfix/ spellings" "bugfix/7-typo" "" "7"
expect "keyword with colon" "chore/cleanup" "Closes: #8" "8"
expect "keyword without colon, mixed case" "chore/cleanup" "FIXED #9" "9"
expect "each Closes pair counts" "chore/cleanup" $'Closes #1\nFixes #2, closes #3' "1 2 3"
expect "branch and body dedupe" "fix/5-x" "Resolves #5" "5"
expect "leading zeros normalised" "fix/007-x" "" "7"

# Should-fail witnesses: each must close nothing.
expect "hotfix #5 is not a keyword" "chore/x" "hotfix #5" ""
expect "prefix #12 is not a keyword" "chore/x" "prefix #12" ""
expect "not fix #12" "chore/x" "This does not fix #12 yet" ""
expect "won't close #9" "chore/x" "we won't close #9" ""
expect "never resolves #4" "chore/x" "never resolves #4" ""
expect "does not fully fix #12" "chore/x" "This does not fully fix #12" ""
expect "won't actually close #9" "chore/x" "we won't actually close #9" ""
expect "never really resolves #3" "chore/x" "it never really resolves #3" ""
expect "negation elsewhere in the sentence" "chore/x" "Not a hotfix, closes #6" "6"
expect "negation in an earlier sentence" "chore/x" $'It is not done yet.\nFixes #7' "7"
expect "list form closes only the first" "chore/x" "Closes #1, #2" "1"
expect "cross-repo ref ignored" "chore/x" "Closes owner/repo#40" ""
expect "digits glued to letters ignored" "chore/x" "Closes #12abc" ""
expect "year in leading form" "chore/2026-10-cleanup" "" ""
expect "unknown prefix in leading form" "user/42-wip" "" ""
expect "deps/ prefix in leading form" "deps/3-bump" "" ""
expect "trailing -N is no longer read (node)" "chore/bump-node-20" "" ""
expect "trailing -N is no longer read (python)" "fix/python-3-12" "" ""
expect "trailing -N is no longer read (v)" "feat/oauth2-v-3" "" ""
expect "dependabot body quoting upstream Fixes" "dependabot/npm/foo-4" "Fixes #1234" ""
expect "renovate body quoting upstream closes" "renovate/foo" "closes #87" ""
expect "release branch body" "release/1.2.3" "Closes #5" ""
expect "no number at all" "feat/add-thing" "just prose" ""

# Workflow wiring: a workflow that calls a file it never fetched fails on every run.
str_wf="$REPO_ROOT/templates/common/.github/workflows/close-linked-issues.yml"
str_called=$(sed -nE 's/^ *run: bash (bin\/[a-z_]+\.sh)$/\1/p' "$str_wf")
if [[ -f "$REPO_ROOT/templates/common/$str_called" ]] && grep -q 'uses: actions/checkout@' "$str_wf"; then
	echo "ok   - workflow checks out the repo and calls an existing script"
else
	echo "FAIL - workflow calls '$str_called' without a checkout, or the script is missing"
	int_failures=$((int_failures + 1))
fi

# Error handling, against a stub gh. STUB_API=<404|500|open>, STUB_CLOSE_FAIL=<number>.
str_bin="$(mktemp -d)"
trap 'rm -rf "$str_bin"' EXIT
cat >"$str_bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1" == "api" ]]; then
	case "$STUB_API" in
		404) echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
		500) echo "gh: Server Error (HTTP 500)" >&2; exit 1 ;;
		*) echo "open"; exit 0 ;;
	esac
fi
echo "$*" >>"$STUB_LOG"
[[ "$3" == "$STUB_CLOSE_FAIL" ]] && exit 1
exit 0
STUB
chmod +x "$str_bin/gh"

# run_script <STUB_API> <STUB_CLOSE_FAIL> <body> -> sets int_status and str_log
run_script() {
	STUB_LOG="$str_bin/log"
	: >"$STUB_LOG"
	PATH="$str_bin:$PATH" STUB_API="$1" STUB_CLOSE_FAIL="$2" STUB_LOG="$STUB_LOG" \
		BRANCH="chore/x" BODY="$3" PR="99" GH_REPO="o/r" bash "$SCRIPT" >/dev/null 2>&1
	int_status=$?
	str_log=$(<"$STUB_LOG")
}

check() {
	# check <description> <condition: 0 = holds>
	if [[ "$2" -eq 0 ]]; then
		echo "ok   - $1"
		return 0
	fi
	echo "FAIL - $1"
	int_failures=$((int_failures + 1))
}

run_script 404 "" "Closes #1"
check "404 is swallowed, job green, nothing closed" "$((int_status != 0 || ${#str_log} != 0))"

run_script 500 "" "Closes #1"
check "a 500 fails the job" "$((int_status == 0))"

run_script open 1 $'Closes #1\nCloses #2'
check "one failed close does not abort the rest" "$([[ "$str_log" == *"issue close 2"* ]] && echo 0 || echo 1)"
check "one failed close fails the job" "$((int_status == 0))"

run_script open "" "Closes #99"
check "the PR's own number is skipped" "${#str_log}"

if ((int_failures > 0)); then
	echo "$int_failures failure(s)"
	exit 1
fi
echo "all passed"

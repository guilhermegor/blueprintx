#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/templates/common/bin/dependabot_auto_merge.sh"

GH_REPO=o/r
STUB_AUTHOR="dependabot[bot]"
good_commit='{"author":{"login":"dependabot[bot]"},"committer":{"login":"web-flow"},"commit":{"verification":{"verified":true}}}'
forged_commit='{"author":{"login":"dependabot[bot]"},"committer":{"login":"mallory"},"commit":{"verification":{"verified":false}}}'
human_signed_commit='{"author":{"login":"dependabot[bot]"},"committer":{"login":"mallory"},"commit":{"verification":{"verified":true}}}'
unverified_webflow_commit='{"author":{"login":"dependabot[bot]"},"committer":{"login":"web-flow"},"commit":{"verification":{"verified":false}}}'
human_commit='{"author":{"login":"human"},"committer":{"login":"web-flow"},"commit":{"verification":{"verified":true}}}'
STUB_COMMITS="[$good_commit]"
STUB_RUNS='{"total_count":1,"workflow_runs":[{"actor":{"login":"dependabot[bot]"}}]}'
STUB_REVIEWS='[]'
CALLS_FILE=$(mktemp)
STUB_CALLS=""
STUB_BASE_ROSTER='reviewers:
  - login: coderabbitai[bot]
    posts: threads
  - login: github-actions[bot]
    posts: status
  - login: guilhermegor-review-ladder[bot]
    posts: threads'
STUB_HEAD_ROSTER_EXTRA='  - login: evil-bot[bot]
    posts: threads'

gh() {
	case "$*" in
	*"contents/.review-bots.yaml"*) [[ -n "${STUB_NO_ROSTER:-}" ]] && return 1 ;;&
	*"contents/.review-bots.yaml?ref=basesha"*) printf '%s\n' "$STUB_BASE_ROSTER" ;;
	*"contents/.review-bots.yaml"*) printf '%s\n%s\n' "$STUB_BASE_ROSTER" "$STUB_HEAD_ROSTER_EXTRA" ;;
	"pr merge"*)
		printf "%s ;" "$*" >>"$CALLS_FILE"
		[[ -n "${STUB_DISARM_ERR:-}" && "$*" == *--disable-auto* ]] && { echo "$STUB_DISARM_ERR" >&2; return 1; }
		return 0
		;;
	*"actions/runs"*) printf '%s\n' "$STUB_RUNS" ;;
	*"/commits"*)
		printf '%s\n' "$STUB_COMMITS"
		;;
	*"/reviews"*) printf '%s\n' "$STUB_REVIEWS" ;;
	*"/pulls/"*) printf '{"user":{"login":"%s"},"base":{"sha":"basesha"}}\n' "$STUB_AUTHOR" ;;
	*)
		echo "UNEXPECTED gh $*" >&2
		return 1
		;;
	esac
}

int_failures=0
check() {
	local str_desc="$1" str_want="$2" str_got="$3"
	if [[ "$str_got" == "$str_want" ]]; then
		echo "ok   - $str_desc"
		return 0
	fi
	echo "FAIL - $str_desc: want '$str_want', got '$str_got'"
	int_failures=$((int_failures + 1))
}
expect() { check "$1" "$2" "$(decide 1 abc "$3")"; }
run_main() {
	: >"$CALLS_FILE"
	PR=1 HEAD_SHA=abc DEPS_JSON="$1" main >/dev/null 2>&1
	local int_rc=$?
	STUB_CALLS=$(cat "$CALLS_FILE")
	return "$int_rc"
}

patch='[{"updateType":"version-update:semver-patch"}]'
minor='[{"updateType":"version-update:semver-minor"}]'
major='[{"updateType":"version-update:semver-major"}]'
grouped='[{"updateType":"version-update:semver-minor"},{"updateType":"version-update:semver-major"}]'

expect "patch arms" arm "$patch"
expect "minor arms" arm "$minor"
expect "major without review waits" wait-review "$major"
expect "grouped with one major waits" wait-review "$grouped"
expect "empty metadata waits (fail-closed)" wait-review ""
expect "garbage metadata waits (fail-closed)" wait-review "not json"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"owner"},"author_association":"MEMBER","state":"APPROVED"}]'
expect "major with a review on head arms" arm "$major"
STUB_NO_ROSTER=1
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"owner"},"author_association":"MEMBER","state":"APPROVED"}]'
expect "missing roster still lets a trusted human review arm a major" arm "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"coderabbitai[bot]","type":"Bot"},"author_association":"NONE","state":"COMMENTED"}]'
expect "missing roster trusts no bot" wait-review "$major"
STUB_NO_ROSTER=""
STUB_REVIEWS='[{"commit_id":"old","user":{"login":"owner"},"author_association":"MEMBER","state":"APPROVED"}]'
expect "major reviewed at an older head waits" wait-review "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"stranger"},"author_association":"NONE","state":"APPROVED"},{"commit_id":"abc","user":{"login":"c"},"author_association":"CONTRIBUTOR","state":"APPROVED"}]'
expect "major reviewed only by NONE/CONTRIBUTOR waits" wait-review "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"owner"},"author_association":"OWNER","state":"CHANGES_REQUESTED"},{"commit_id":"abc","user":{"login":"m"},"author_association":"MEMBER","state":"APPROVED"}]'
expect "major with a trusted CHANGES_REQUESTED waits" wait-review "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"dependabot[bot]"},"author_association":"NONE","state":"COMMENTED"}]'
expect "major reviewed only by dependabot waits" wait-review "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"owner"},"author_association":"MEMBER","state":"PENDING"}]'
expect "major with a pending review waits" wait-review "$major"
bot_review() { printf '[{"commit_id":"%s","user":{"login":"%s","type":"%s"},"author_association":"NONE","state":"COMMENTED"}]' "$1" "$2" "$3"; }
STUB_REVIEWS=$(bot_review abc "guilhermegor-review-ladder[bot]" Bot)
expect "roster bot review on head arms a major" arm "$major"
STUB_REVIEWS=$(bot_review abc "coderabbitai[bot]" Bot)
expect "second roster bot arms a major" arm "$major"
STUB_REVIEWS=$(bot_review abc "random-bot[bot]" Bot)
expect "non-roster bot does not arm a major" wait-review "$major"
STUB_REVIEWS=$(bot_review abc "coderabbitai[bot]" User)
expect "User named like a roster bot does not arm a major" wait-review "$major"
STUB_REVIEWS=$(bot_review abc "evil-bot[bot]" Bot)
expect "bot added to the roster only on the PR head does not arm" wait-review "$major"
STUB_REVIEWS=$(bot_review abc "github-actions[bot]" Bot)
expect "status-only roster member does not arm a major" wait-review "$major"
STUB_REVIEWS=$(bot_review old "coderabbitai[bot]" Bot)
expect "roster bot review on an older head does not arm" wait-review "$major"
STUB_REVIEWS='[]'
STUB_AUTHOR="mallory"
expect "non-dependabot author is skipped" skip "$patch"
STUB_AUTHOR="dependabot[bot]"
STUB_COMMITS="[$good_commit,$human_commit]"
expect "human commit on a dependabot branch is skipped" skip "$minor"
STUB_COMMITS="[$forged_commit]"
expect "forged author with an unverified signature is skipped" skip "$minor"
STUB_COMMITS="[$human_signed_commit]"
expect "verified commit by a human committer is skipped" skip "$minor"
STUB_COMMITS="[$unverified_webflow_commit]"
expect "web-flow committer without a verified signature is skipped" skip "$minor"
STUB_COMMITS="[]"
expect "empty commit list is skipped" skip "$minor"
STUB_COMMITS="[$good_commit]"
expect "genuine dependabot commit shape is armed" arm "$minor"
STUB_RUNS='{"total_count":1,"workflow_runs":[{"actor":{"login":"mallory"}}]}'
expect "genuine-looking commit pushed by a human is skipped" skip "$minor"
STUB_RUNS=''
expect "unreadable run actor is skipped" skip "$minor"
STUB_RUNS='{"total_count":0,"workflow_runs":[]}'
expect "no run for the head is skipped" skip "$minor"
STUB_RUNS='{"total_count":1,"workflow_runs":[{"actor":{"login":"dependabot[bot]"}}]}'
EVENT_NAME=pull_request_target SENDER=mallory
expect "pull_request_target synchronize by a human is skipped" skip "$minor"
run_main "$minor"
check "human synchronize disarms" "pr merge 1 --disable-auto --repo o/r ;" "$STUB_CALLS"
EVENT_NAME=pull_request_target SENDER="dependabot[bot]"
STUB_RUNS=''
expect "pull_request_target by dependabot is armed" arm "$minor"
EVENT_NAME=""; SENDER=""
STUB_RUNS='{"total_count":1,"workflow_runs":[{"actor":{"login":"dependabot[bot]"}}]}'

STUB_COMMITS="[$good_commit]"
run_main "$patch"
check "patch arms auto-merge" "pr merge 1 --auto --squash --match-head-commit abc --repo o/r ;" "$STUB_CALLS"
run_main "$major"
check "unreviewed major disarms" "pr merge 1 --disable-auto --repo o/r ;" "$STUB_CALLS"
STUB_COMMITS="[$good_commit,$human_commit]"
run_main "$minor"
check "human commit disarms a previously armed PR" "pr merge 1 --disable-auto --repo o/r ;" "$STUB_CALLS"

str_tmp=$(mktemp -d)
trap 'rm -rf "$str_tmp"' EXIT
(
	source "$REPO_ROOT/bin/lib/common.sh"
	copy_dependabot_auto_merge "$str_tmp" >/dev/null
)
str_script=$(sed -nE 's/.*run: bash (.*)$/\1/p' "$str_tmp/.github/workflows/dependabot-auto-merge.yml")
[[ -f "$str_tmp/$str_script" ]]
check "generated workflow runs a script that exists in the generated tree" 0 "$?"
str_script=$(sed -nE 's/.*run: bash (.*)$/\1/p' "$REPO_ROOT/.github/workflows/dependabot-auto-merge.yml")
[[ -f "$REPO_ROOT/$str_script" ]]
check "root workflow runs a script that exists in this repo" 0 "$?"

for str_wf in .github/workflows/review_threads.yml templates/*/.github/workflows/review[-_]threads.y*ml; do
	grep -qE '^  actions: (read|write)' "$REPO_ROOT/$str_wf"
	check "$str_wf grants actions: for the pusher lookup" 0 "$?"
done

for str_wf in .github/workflows/dependabot-auto-merge.yml templates/common/.github/workflows/dependabot-auto-merge.yml; do
	awk '/id: metadata/ {f=1} f && /continue-on-error: true/ {ok=1} /Checkout base/ {f=0} END {exit !ok}' "$REPO_ROOT/$str_wf"
	check "$str_wf lets a failing metadata step still reach the disarm path" 0 "$?"
	grep -q 'ref: ${{ github.event.pull_request.base.sha }}' "$REPO_ROOT/$str_wf"
	check "$str_wf checks out the base sha, where the script runs" 0 "$?"
done

STUB_DISARM_ERR="GraphQL: Pull request Auto merge is not enabled"
run_main "$major"
check "disarm tolerates 'not enabled'" 0 "$?"
STUB_DISARM_ERR="HTTP 502 bad gateway"
run_main "$major"
check "a real disarm failure fails the job" 1 "$?"
STUB_DISARM_ERR=""

STUB_AUTHOR="dependabot[bot]"
STUB_COMMITS="[$good_commit]"
STUB_REVIEWS='[{"commit_id":"old","user":{"login":"owner"},"author_association":"OWNER","state":"CHANGES_REQUESTED"},{"commit_id":"abc","user":{"login":"m"},"author_association":"MEMBER","state":"APPROVED"}]'
expect "a standing trusted block from an older head still blocks" wait-review "$major"
STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"owner"},"author_association":"OWNER","state":"CHANGES_REQUESTED"},{"commit_id":"abc","user":{"login":"owner"},"author_association":"OWNER","state":"APPROVED"}]'
expect "the same reviewer approving after requesting changes arms" arm "$major"

STUB_REVIEWS='[{"commit_id":"old","user":{"login":"owner"},"author_association":"OWNER","state":"CHANGES_REQUESTED"},{"commit_id":"abc","user":{"login":"owner"},"author_association":"OWNER","state":"COMMENTED"}]'
expect "a later COMMENTED does not clear a standing CHANGES_REQUESTED" wait-review "$major"

for str_wf in .github/workflows/dependabot-auto-merge.yml templates/common/.github/workflows/dependabot-auto-merge.yml; do
	grep -qE '^      actions: read' "$REPO_ROOT/$str_wf"
	check "$str_wf grants actions: read for the pusher lookup" 0 "$?"
	grep -q '^concurrency:' "$REPO_ROOT/$str_wf"
	check "$str_wf serialises runs per PR" 0 "$?"
done

STUB_REVIEWS='[{"commit_id":"abc","user":{"login":"some-app[bot]","type":"Bot"},"author_association":"COLLABORATOR","state":"APPROVED"}]'
expect "a Bot with a collaborator association is not a trusted human" wait-review "$major"

for str_wf in .github/workflows/dependabot-auto-merge.yml templates/common/.github/workflows/dependabot-auto-merge.yml; do
	grep -q 'types: \[submitted, dismissed\]' "$REPO_ROOT/$str_wf"
	check "$str_wf re-evaluates on a dismissed review" 0 "$?"
done

diff <(sed 's#bin/dependabot_auto_merge.sh#X#' "$REPO_ROOT/.github/workflows/dependabot-auto-merge.yml" | sed 's#templates/common/X#X#') \
	<(sed 's#bin/dependabot_auto_merge.sh#X#' "$REPO_ROOT/templates/common/.github/workflows/dependabot-auto-merge.yml") >/dev/null
check "root and template workflows differ only in the script path" 0 "$?"

((int_failures == 0)) || exit 1

#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/templates/common/bin/dependabot_auto_merge.sh"

GH_REPO=o/r
STUB_AUTHOR="dependabot[bot]"
STUB_COMMIT_AUTHORS='"dependabot[bot]"'
STUB_REVIEWS='[]'
STUB_CALLS=""

gh() {
	case "$*" in
	"pr merge"*) STUB_CALLS+="$* ;" ;;
	*"/commits"*)
		printf '[%s]\n' "$(printf '%s' "$STUB_COMMIT_AUTHORS" | sed -E 's/("[^"]*")/{"author":{"login":\1}}/g')"
		;;
	*"/reviews"*) printf '%s\n' "$STUB_REVIEWS" ;;
	*"/pulls/"*) printf '{"user":{"login":"%s"}}\n' "$STUB_AUTHOR" ;;
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
	STUB_CALLS=""
	PR=1 HEAD_SHA=abc DEPS_JSON="$1" main >/dev/null
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
STUB_REVIEWS='[]'
STUB_AUTHOR="mallory"
expect "non-dependabot author is skipped" skip "$patch"
STUB_AUTHOR="dependabot[bot]"
STUB_COMMIT_AUTHORS='"dependabot[bot]","human"'
expect "human commit on a dependabot branch is skipped" skip "$minor"

STUB_COMMIT_AUTHORS='"dependabot[bot]"'
run_main "$patch"
check "patch arms auto-merge" "pr merge 1 --auto --squash --match-head-commit abc --repo o/r ;" "$STUB_CALLS"
run_main "$major"
check "unreviewed major disarms" "pr merge 1 --disable-auto --repo o/r ;" "$STUB_CALLS"
STUB_COMMIT_AUTHORS='"dependabot[bot]","human"'
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

((int_failures == 0)) || exit 1

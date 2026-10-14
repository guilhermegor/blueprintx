#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/templates/common/bin/dependabot_auto_merge.sh"

GH_REPO=o/r
STUB_AUTHOR="dependabot[bot]"
STUB_BAD_COMMITS=0
STUB_REVIEWS=0

gh() {
	case "$*" in
	*"/commits"*) echo "$STUB_BAD_COMMITS" ;;
	*"/reviews"*) echo "$STUB_REVIEWS" ;;
	*"/pulls/"*) echo "$STUB_AUTHOR" ;;
	*) echo "UNEXPECTED gh $*" >&2; return 1 ;;
	esac
}

int_failures=0
expect() {
	local str_desc="$1" str_want="$2" str_json="$3" str_got
	str_got=$(decide 1 abc "$str_json")
	if [[ "$str_got" == "$str_want" ]]; then
		echo "ok   - $str_desc"
		return 0
	fi
	echo "FAIL - $str_desc: want '$str_want', got '$str_got'"
	int_failures=$((int_failures + 1))
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
STUB_REVIEWS=1
expect "major with a review on head arms" arm "$major"
STUB_REVIEWS=0
STUB_AUTHOR="mallory"
expect "non-dependabot author is skipped" skip "$patch"
STUB_AUTHOR="dependabot[bot]"
STUB_BAD_COMMITS=1
expect "human commit on a dependabot branch is skipped" skip "$minor"

((int_failures == 0)) || exit 1

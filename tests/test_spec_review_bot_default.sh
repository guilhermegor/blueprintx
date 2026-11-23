#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR_SCRATCH="$(mktemp -d)"
trap 'rm -rf "$DIR_SCRATCH"' EXIT

int_failures=0

check() {
	if ! "$@"; then
		echo "FAIL: $*" >&2
		int_failures=$((int_failures + 1))
	fi
}

printf 'tier: lib-minimal\n' >"$DIR_SCRATCH/empty.spec"
printf 'review_bot_roster=n\n' >"$DIR_SCRATCH/optout.spec"

str_default="$(bash -c 'source "$1/bin/lib/spec.sh"; _spec_answer_review_bot "$2"' _ "$REPO_ROOT" "$DIR_SCRATCH/empty.spec")"
str_optout="$(bash -c 'source "$1/bin/lib/spec.sh"; _spec_answer_review_bot "$2"' _ "$REPO_ROOT" "$DIR_SCRATCH/optout.spec")"

check [ "$str_default" = "y" ]
check [ "$str_optout" = "n" ]
check_absent() {
	! grep -q -- "$1" "$2"
}

check check_absent 'review_bot_roster:n' "$REPO_ROOT/bin/lib/spec.sh"
check check_absent 'Human-only review' "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"

[ "$int_failures" -eq 0 ] || exit 1
echo "OK: review_bot_roster defaults to y in specs"

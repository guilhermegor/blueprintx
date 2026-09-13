#!/bin/bash
# Should-fail/should-pass witness for the review-bot roster opt-out (blueprintx#374).
#
# The dangerous direction is a FALSE SHIP: INCLUDE_REVIEW_BOT_ROSTER=false (the scaffold
# answered "no reviewer bot") must still omit .review-bots.yaml from the generated project —
# shipping it anyway silently restores the unsatisfiable required check this fixes. See
# docs/faq.md ("I don't use a PR review bot...") for the full rationale.
#
# Usage:  bash bin/ci/check_review_bot_roster_optout.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_python_templates.sh
source "$REPO_ROOT/bin/lib/scaffold_python_templates.sh"

# Read by scaffold_copy_tooling_configs (a different file), which shellcheck cannot follow.
# shellcheck disable=SC2034
COMMON_TEMPLATE_ROOT="$REPO_ROOT/templates/python-common"
int_failures=0

expect_python_roster() {
	# $1 = INCLUDE_REVIEW_BOT_ROSTER value, $2 = expected outcome (present|absent)
	local str_flag="$1" str_want="$2" str_project str_got="absent"
	str_project="$(mktemp -d)"
	INCLUDE_REVIEW_BOT_ROSTER="$str_flag" scaffold_copy_tooling_configs "$str_project" >/dev/null 2>&1 || true
	[ -f "$str_project/.review-bots.yaml" ] && str_got="present"
	rm -rf "$str_project"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" \
			"scaffold_copy_tooling_configs with INCLUDE_REVIEW_BOT_ROSTER=$str_flag → $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
	fi
}

expect_ts_roster() {
	# $1 = INCLUDE_REVIEW_BOT_ROSTER value, $2 = expected outcome (present|absent)
	local str_flag="$1" str_want="$2" str_project str_got="absent"
	str_project="$(mktemp -d)"
	mkdir -p "$str_project/.github"
	: >"$str_project/.github/.review-bots.yaml"
	INCLUDE_REVIEW_BOT_ROSTER="$str_flag" scaffold_prune_review_bot_roster "$str_project"
	[ -f "$str_project/.github/.review-bots.yaml" ] && str_got="present"
	rm -rf "$str_project"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" \
			"scaffold_prune_review_bot_roster with INCLUDE_REVIEW_BOT_ROSTER=$str_flag → $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
	fi
}

main() {
	expect_python_roster "false" "absent"   # the fix: "no" omits the file
	expect_python_roster "true" "present"   # the default: unchanged behaviour
	expect_ts_roster "false" "absent"
	expect_ts_roster "true" "present"

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures review-bot roster opt-out assertion(s) failed"
		exit 1
	fi
	print_status "success" "review-bot roster opt-out: 'no' omits the file, 'yes' ships it, on both scaffold shapes"
}

main "$@"

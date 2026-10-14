#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_python_templates.sh
source "$REPO_ROOT/bin/lib/scaffold_python_templates.sh"

# shellcheck disable=SC2034
COMMON_TEMPLATE_ROOT="$REPO_ROOT/templates/python-common"
# shellcheck disable=SC2034
SHARED_TEMPLATE_ROOT="$REPO_ROOT/templates/common"
int_failures=0

expect_python_roster() {
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
	local str_flag="$1" str_want="$2" str_project str_got="absent"
	str_project="$(mktemp -d)"
	cp -r "$REPO_ROOT/templates/ts-common/.github/." "$str_project/.github"
	INCLUDE_REVIEW_BOT_ROSTER="$str_flag" scaffold_prune_review_bot_roster "$str_project"
	[ -f "$str_project/.github/.review-bots.yaml" ] && str_got="present"
	rm -rf "$str_project"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" \
			"scaffold_prune_review_bot_roster with INCLUDE_REVIEW_BOT_ROSTER=$str_flag → $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
	fi
}

expect_lib_minimal_roster() {
	local str_flag="$1" str_want="$2" str_project str_got="absent" str_fn
	str_fn="$(awk '/^lib_minimal_copy_tooling_configs\(\)/,/^}/' "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh")"
	if [ -z "$str_fn" ]; then
		print_status "error" "lib_minimal_copy_tooling_configs not found in python_lib_minimal.sh"
		int_failures=$((int_failures + 1))
		return
	fi
	eval "$str_fn"
	str_project="$(mktemp -d)"
	INCLUDE_REVIEW_BOT_ROSTER="$str_flag" BLUEPRINTX_ROOT="$REPO_ROOT" \
		lib_minimal_copy_tooling_configs "$str_project" >/dev/null 2>&1 || true
	[ -f "$str_project/.review-bots.yaml" ] && str_got="present"
	rm -rf "$str_project"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" \
			"lib_minimal_copy_tooling_configs with INCLUDE_REVIEW_BOT_ROSTER=$str_flag → $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
	fi
}

main() {
	expect_python_roster "false" "absent"
	expect_python_roster "true" "present"
	expect_ts_roster "false" "absent"
	expect_ts_roster "true" "present"
	expect_lib_minimal_roster "false" "absent"
	expect_lib_minimal_roster "true" "present"

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures review-bot roster opt-out assertion(s) failed"
		exit 1
	fi
	print_status "success" "review-bot roster opt-out: 'no' omits the file, 'yes' ships it, on all three scaffold shapes"
}

main "$@"

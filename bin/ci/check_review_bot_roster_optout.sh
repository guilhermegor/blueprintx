#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_python_templates.sh
source "$REPO_ROOT/bin/lib/scaffold_python_templates.sh"

# shellcheck disable=SC2034  # read by scaffold_copy_tooling_configs, which shellcheck cannot follow
COMMON_TEMPLATE_ROOT="$REPO_ROOT/templates/python-common"
# shellcheck disable=SC2034  # also read by scaffold_copy_tooling_configs (#540)
SHARED_TEMPLATE_ROOT="$REPO_ROOT/templates/common"
BLUEPRINTX_ROOT="$REPO_ROOT"
int_failures=0

roster_state() {
	if [ ! -f "$1" ]; then
		echo absent
	elif grep -qx 'adopted: false' "$1"; then
		echo optout
	else
		echo present
	fi
}

expect_python_roster() {
	local str_flag="$1" str_want="$2" str_project str_got="absent"
	str_project="$(mktemp -d)"
	INCLUDE_REVIEW_BOT_ROSTER="$str_flag" scaffold_copy_tooling_configs "$str_project" >/dev/null 2>&1 || true
	str_got="$(roster_state "$str_project/.review-bots.yaml")"
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
	str_got="$(roster_state "$str_project/.github/.review-bots.yaml")"
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
	str_got="$(roster_state "$str_project/.review-bots.yaml")"
	rm -rf "$str_project"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" \
			"lib_minimal_copy_tooling_configs with INCLUDE_REVIEW_BOT_ROSTER=$str_flag → $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
	fi
}

main() {
	expect_python_roster "false" "optout"
	expect_python_roster "true" "present"
	expect_ts_roster "false" "optout"
	expect_ts_roster "true" "present"
	expect_lib_minimal_roster "false" "optout"
	expect_lib_minimal_roster "true" "present"

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures review-bot roster opt-out assertion(s) failed"
		exit 1
	fi
	print_status "success" "review-bot roster opt-out: 'no' ships an adopted: false roster, 'yes' ships the real one, on all three scaffold shapes"
}

main "$@"

#!/bin/bash

scaffold_enable_delete_branch_on_merge() {
	local str_slug="$1"
	local str_state

	gh api -X PATCH "repos/${str_slug}" -F delete_branch_on_merge=true >/dev/null 2>&1 || true
	str_state="$(gh api "repos/${str_slug}" --jq .delete_branch_on_merge 2>/dev/null || true)"
	if [ "$str_state" = "true" ]; then
		print_status "success" "delete_branch_on_merge enabled on ${str_slug}"
		return 0
	fi
	print_status "warning" \
		"Could not confirm delete_branch_on_merge on ${str_slug} - enable it in the repo settings"
	return 0
}

#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

PROTECTED_BRANCHES=("main" "master")

current_branch() {
	git rev-parse --abbrev-ref HEAD 2>/dev/null || true
}

is_protected() {
	local str_branch="$1"
	[[ " ${PROTECTED_BRANCHES[*]} " == *" $str_branch "* ]]
}

main() {
	local str_branch
	str_branch="$(current_branch)"

	if [[ -z "$str_branch" || "$str_branch" == "HEAD" ]]; then
		exit 0
	fi

	if ! is_protected "$str_branch"; then
		exit 0
	fi

	print_status "error" "Direct commits to the protected branch '$str_branch' are not allowed."
	print_status "info" "Create a working branch before committing:"
	print_status "info" "    poe new_branch feat/my-feature"
	exit 1
}

main "$@"

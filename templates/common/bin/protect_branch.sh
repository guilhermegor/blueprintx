#!/bin/bash
# Pre-commit guard: block direct commits to the default branch (main/master) and
# point the user at the project's branch-creation workflow. This is a convenience
# guard rail, not a security control — it can be bypassed with `git commit
# --no-verify` and only runs when the pre-commit hooks are installed.
#
# Offline-only: this hook ships only when a project is scaffolded WITHOUT a
# GitHub remote (apply_offline_mode swaps it in for the stock no-commit-to-branch
# hook). Online projects rely on GitHub server-side branch protection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Branches that must not receive direct commits.
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

	# Detached HEAD or unresolved branch: not a protected branch, let it through.
	if [[ -z "$str_branch" || "$str_branch" == "HEAD" ]]; then
		exit 0
	fi

	if ! is_protected "$str_branch"; then
		exit 0
	fi

	print_status "error" "Direct commits to the protected branch '$str_branch' are not allowed."
	print_status "info" "Create a working branch before committing:"
	print_status "info" "    make new_branch NAME=feat/my-feature"
	print_status "info" "    (without make: ./tasks.sh new_branch feat/my-feature)"
	exit 1
}

main "$@"

#!/usr/bin/env bash
# Create a new feature branch off the default branch (main or master).
# Flow: resolve default branch → checkout it → fast-forward pull when a remote
# exists → validate the CONTRIBUTING branch prefix → create and checkout it.
#
# Branch name: first argument, the NAME=<name> env var, or an interactive prompt.
# Override the base branch with DEFAULT_BRANCH=<name>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Allowed branch prefixes (kept in sync with CONTRIBUTING.md).
BRANCH_PREFIX_PATTERN='^(feat|fix|docs|refactor|chore|hotfix|release)/.+'

ensure_git_repo() {
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		print_status "error" "Current directory is not inside a Git repository."
		exit 1
	fi
}

resolve_branch_name() {
	local str_name="${1:-${NAME:-}}"

	if [[ -z "$str_name" ]]; then
		read -r -p "New branch name (e.g. feat/my-feature): " str_name || true
	fi

	str_name="${str_name#"${str_name%%[![:space:]]*}"}"
	str_name="${str_name%"${str_name##*[![:space:]]}"}"

	if [[ -z "$str_name" ]]; then
		print_status "error" "No branch name provided."
		exit 1
	fi

	if [[ ! "$str_name" =~ $BRANCH_PREFIX_PATTERN ]]; then
		print_status "error" "Invalid branch name '$str_name'."
		print_status "error" "Use one of: feat/ fix/ docs/ refactor/ chore/ hotfix/ release/ followed by a description."
		exit 1
	fi

	echo "$str_name"
}

has_remote() {
	[[ -n "$(git remote 2>/dev/null)" ]]
}

update_base_branch() {
	local str_base="$1"

	print_status "info" "Checking out '$str_base'..."
	if ! git checkout "$str_base"; then
		print_status "error" "Failed to checkout '$str_base'."
		exit 1
	fi

	if has_remote && git rev-parse --abbrev-ref "@{upstream}" >/dev/null 2>&1; then
		print_status "info" "Fast-forwarding '$str_base' from its upstream..."
		git pull --ff-only || print_status "warning" "Could not fast-forward '$str_base' — continuing with the local tip."
	fi
}

create_branch() {
	local str_branch="$1"

	if git show-ref --verify --quiet "refs/heads/$str_branch"; then
		print_status "error" "Branch '$str_branch' already exists."
		exit 1
	fi

	print_status "info" "Creating and checking out '$str_branch'..."
	if ! git checkout -b "$str_branch"; then
		print_status "error" "Failed to create branch '$str_branch'."
		exit 1
	fi

	print_status "success" "On new branch '$str_branch' (from '$2')."
}

main() {
	local str_base_branch
	local str_branch_name

	ensure_git_repo

	str_base_branch="$(resolve_default_branch)"
	print_status "config" "Base branch resolved to '$str_base_branch'."
	str_branch_name="$(resolve_branch_name "${1:-}")"

	update_base_branch "$str_base_branch"
	create_branch "$str_branch_name" "$str_base_branch"
}

main "$@"

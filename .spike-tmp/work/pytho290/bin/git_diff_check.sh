#!/usr/bin/env bash
# Preview whether a .diff applies cleanly to the current working tree, without
# modifying any files. Usage: git_diff_check.sh <path-to.diff>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

ensure_git_repo() {
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		print_status "error" "Not inside a git repository"
		exit 1
	fi
}

main() {
	local str_file="${1:-}"
	if [ -z "$str_file" ]; then
		print_status "error" "Usage: git_diff_check.sh <path-to.diff>"
		exit 1
	fi
	if [ ! -f "$str_file" ]; then
		print_status "error" "File not found: $str_file"
		exit 1
	fi

	ensure_git_repo

	if git apply --check "$str_file"; then
		print_status "success" "Patch applies cleanly: $str_file"
	else
		print_status "error" "Patch does NOT apply cleanly: $str_file"
		exit 1
	fi
}

main "$@"

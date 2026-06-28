#!/usr/bin/env bash
# Export commits in DIFF_RANGE (default main..HEAD) as a dated .diff for
# offline / email transfer. Output lands in DIFF_DIR (default ./git_diffs).

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
	ensure_git_repo

	local str_range="${DIFF_RANGE:-main..HEAD}"
	local str_diff_dir="${DIFF_DIR:-./git_diffs}"
	local str_branch str_branch_kebab str_diff_file
	str_branch=$(git rev-parse --abbrev-ref HEAD)
	str_branch_kebab="${str_branch//\//-}"
	str_diff_file="${str_diff_dir}/${str_branch_kebab}_$(date +%Y%m%d_%H%M%S).diff"

	mkdir -p "$str_diff_dir"
	git format-patch "$str_range" --stdout >"$str_diff_file"

	if [ ! -s "$str_diff_file" ]; then
		rm -f "$str_diff_file"
		print_status "error" "No commits in range '$str_range' — nothing exported"
		exit 1
	fi

	print_status "success" "Diff written: $str_diff_file"
}

main "$@"

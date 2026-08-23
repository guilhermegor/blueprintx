#!/bin/bash
# Reject filenames containing characters outside [a-zA-Z0-9._-].
#
# TWO CALLERS, TWO ARGUMENT SHAPES:
#   pre-commit  → passes the staged files as arguments (hook `check-unix-filenames`)
#   poe lint/CI → passes nothing, and this script discovers the whole tree itself
#
# ⚠️ WHY THE NO-ARG MODE EXISTS AT ALL. Before it, `bash bin/check_unix_filenames.sh` with no
# arguments iterated an empty `$@`, left has_errors at 0, and printed "All filenames are valid"
# — a gate reporting success for having examined nothing, in the most literal way available.
# That is the exact failure this gate's own family (lint_actions.sh, lint_docker.sh) is built to
# refuse, so the fix belongs HERE, in the one place both callers route through, rather than as a
# file list assembled at each call site.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

discover_files() {
	# `git ls-files -z` when the tree is a repo (respects .gitignore, so a stray venv or
	# node_modules path never fails the gate), and a find fallback for a scaffold that has not
	# been git-init'd yet — which is precisely how bin/ci/scaffold_lint_test.sh exercises it.
	if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		git ls-files -z
		return 0
	fi
	# ⚠️ THE PRUNE GROUP MUST COME FIRST, with no test before it. A leading `-type f` is false
	# for a DIRECTORY, so the branch short-circuits and `-prune` is never evaluated — find then
	# descends into .venv and node_modules and lints dependency filenames. Measured: the leading
	# form returned .venv/lib/junk.py and node_modules/pkg/index.js; this form returns neither.
	find . \
		\( -path ./.git -o -path ./.venv -o -path ./node_modules \) -prune \
		-o -type f -print0
}

check_unix_filenames() {
	local has_errors=0

	for f in "$@"; do
		if [[ -d "$f" ]] || [[ "$f" == .git/* ]]; then
			continue
		fi

		local str_filename
		str_filename=$(basename "$f")

		if [[ "$str_filename" == *[^a-zA-Z0-9._-]* ]]; then
			print_status "error" "Invalid filename '$str_filename' in path: $f"
			print_status "error" "Only alphanumeric, ., - and _ are allowed in filenames"
			has_errors=1
		fi
	done

	if [[ $has_errors -eq 0 ]]; then
		print_status "success" "All filenames are valid"
		return 0
	fi
	return 1
}

main() {
	if [ "$#" -gt 0 ]; then
		check_unix_filenames "$@" || exit 1
		return 0
	fi

	cd "$SCRIPT_DIR/.."
	local -a list_files=()
	mapfile -d '' -t list_files < <(discover_files)

	# ⚠️ ASSERT THE COUNT, DO NOT TRUST THE EXIT CODE. Zero discovered files is never legitimate
	# here — every project has tracked files — so an empty list means discovery broke, not that
	# the tree is clean. Without this the no-arg mode would reintroduce the vacuous success it
	# was added to remove.
	if [ "${#list_files[@]}" -eq 0 ]; then
		print_status "error" "no files discovered — this gate would pass vacuously"
		exit 1
	fi

	check_unix_filenames "${list_files[@]}" || exit 1
}

main "$@"

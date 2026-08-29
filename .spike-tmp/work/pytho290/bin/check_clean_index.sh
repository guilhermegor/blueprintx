#!/bin/bash
# pre-push guard: refuse to push while the index is non-empty.
#
# Staged-but-uncommitted work at push time is the fingerprint of a commit that was REJECTED
# after `git add` ran. The push then ships the PREVIOUS commit and prints success, so every
# visible signal is green while the work stays behind. It is found only by comparing HEAD to
# origin/<branch> — which nobody does, because nothing suggested anything went wrong.
#
# No other layer can catch this:
#   - CI cannot: it only sees what was pushed, and a commit that does not exist is not a diff.
#   - pre-commit cannot: it already did its job by rejecting the commit; the loss is downstream.
#
# It also closes a hole a WRITTEN RULE did not. The rule ("never pipe `git commit` through
# tail/grep; confirm HEAD moved") existed and was violated anyway, hours after being quoted —
# because the failure mode is a rejection scrolling off screen, which is exactly what a tired
# reader does not notice.
#
# GUARD THE INDEX, NOT THE DIRTY TREE. Unstaged edits while pushing are routine, so blocking
# any dirty tree is noisy and gets disabled — and a guard that gets disabled protects nothing.
# A POPULATED index means `git add` ran and no commit consumed it: nearly false-positive-free,
# which is the property that decides whether a guard survives its first month.
#
# Escape hatch: `git push --no-verify` (or stash the index) for the rare deliberate case.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

main() {
	# No git work tree (a shipped zip) — nothing to guard, and never block.
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		return 0
	fi

	if git diff --cached --quiet; then
		return 0
	fi

	print_status "error" "Push blocked: the index is not empty (staged changes with no commit)."
	print_status "error" "This almost always means a commit was REJECTED after 'git add' ran —"
	print_status "error" "the push would ship the PREVIOUS commit and still print success."
	print_status "error" ""
	print_status "error" "Staged but uncommitted:"
	git diff --cached --name-only | sed 's/^/    /' >&2
	print_status "error" ""
	print_status "error" "Fix: re-run the commit and read its FULL output (never pipe it through"
	print_status "error" "tail/grep — that is how the rejection scrolls off), then confirm HEAD"
	print_status "error" "moved with 'git log --oneline -1'."
	print_status "error" "Deliberate exception: 'git push --no-verify'."
	return 1
}

main "$@"

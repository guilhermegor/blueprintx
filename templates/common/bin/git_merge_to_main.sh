#!/usr/bin/env bash
# Merge the current clean branch into the default branch (main or master) and
# delete it afterwards. Override the target with DEFAULT_BRANCH=<name> or by
# passing the branch name as the first argument.
#
# Offline-only: this script ships only when a project is scaffolded WITHOUT a
# GitHub remote. Online projects merge via GitHub pull requests instead.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# With no remote, `git log` is the only instrument, and it cannot answer "what
# was the target branch immediately before this merge?" — an online repo gets
# that free from its PR list. CHECKPOINTS_FILE is the append-only substitute:
# timestamp, source tip, target-before hash, and the literal reset command.
# ⚠️ ANCHORED TO THE REPO ROOT, not to the caller's directory. `ensure_git_repo` is
# satisfied anywhere inside the work tree, so a run from `src/` would otherwise create and
# stage `src/docs/checkpoints.md` — a second, invisible ledger, while the real one silently
# stops recording.
CHECKPOINTS_FILE="$(git rev-parse --show-toplevel 2>/dev/null || echo .)/docs/checkpoints.md"

ensure_git_repo() {
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		print_status "error" "Current directory is not inside a Git repository."
		exit 1
	fi
}

get_current_branch() {
	local str_branch
	str_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

	if [[ -z "$str_branch" ]]; then
		print_status "error" "Could not determine the current Git branch."
		exit 1
	fi

	if [[ "$str_branch" == "HEAD" ]]; then
		print_status "error" "Detached HEAD detected. Checkout a branch before running this script."
		exit 1
	fi

	echo "$str_branch"
}

ensure_target_branch_exists() {
	local str_target="$1"

	if ! git show-ref --verify --quiet "refs/heads/$str_target"; then
		print_status "error" "Default branch '$str_target' does not exist locally."
		exit 1
	fi
}

get_git_status_porcelain() {
	git status --porcelain --untracked-files=all
}

has_uncommitted_changes() {
	local str_status="$1"

	while IFS= read -r line; do
		[[ -n "$line" ]] || continue
		if [[ "$line" != \?\?* ]]; then
			return 0
		fi
	done <<<"$str_status"

	return 1
}

has_untracked_files() {
	local str_status="$1"

	while IFS= read -r line; do
		[[ -n "$line" ]] || continue
		if [[ "$line" == \?\?* ]]; then
			return 0
		fi
	done <<<"$str_status"

	return 1
}

seed_checkpoints_file() {
	[[ -f "$CHECKPOINTS_FILE" ]] && return 0

	ensure_dir "$(dirname "$CHECKPOINTS_FILE")"
	cat >"$CHECKPOINTS_FILE" <<-'HEADER'
		# Offline merge checkpoints

		Append-only log written by `bin/git_merge_to_main.sh` before every merge. Each
		entry records what the target branch pointed at immediately before that merge —
		the affordance an online repo gets for free from its PR list. To undo a merge,
		run that entry's `git reset --hard` line on the target branch.
	HEADER
}

backup_checkpoints_file() {
	local str_backup
	str_backup="$(mktemp)"
	# An absent file is represented by an absent backup, so restore knows to delete.
	if [[ -f "$CHECKPOINTS_FILE" ]]; then
		cp "$CHECKPOINTS_FILE" "$str_backup"
	else
		rm -f "$str_backup"
	fi
	printf '%s' "$str_backup"
}

restore_checkpoints_file() {
	local str_backup="$1"

	git restore --staged "$CHECKPOINTS_FILE" >/dev/null 2>&1 || true
	if [[ -f "$str_backup" ]]; then
		cp "$str_backup" "$CHECKPOINTS_FILE"
		rm -f "$str_backup"
	else
		rm -f "$CHECKPOINTS_FILE"
	fi
}

record_checkpoint() {
	local str_source="$1"
	local str_target="$2"
	local str_source_tip str_target_before str_backup

	seed_checkpoints_file
	# Snapshot BEFORE appending, so a rejected commit can be undone. Without this the
	# entry stays staged, the next run trips the uncommitted-changes guard and exits
	# before reaching here — making the "re-run" this function advises impossible.
	str_backup="$(backup_checkpoints_file)"

	str_source_tip="$(git rev-parse "$str_source")"
	str_target_before="$(git rev-parse "$str_target")"

	{
		echo ""
		echo "## $(date '+%Y-%m-%d %H:%M:%S') — merge '$str_source' into '$str_target'"
		echo ""
		echo "- source tip: \`$str_source_tip\`"
		echo "- '$str_target' before merge: \`$str_target_before\`"
		echo "- undo: \`git reset --hard $str_target_before\`"
	} >>"$CHECKPOINTS_FILE"

	print_status "info" "Recording checkpoint on '$str_source' — this commit runs the FULL pre-commit gate (lint + unit + integration + coverage) and can take several minutes; give it a timeout of at least 7 minutes."
	git add "$CHECKPOINTS_FILE"
	if ! git commit -m "chore: record merge checkpoint for '$str_source' -> '$str_target'"; then
		restore_checkpoints_file "$str_backup"
		print_status "error" "Checkpoint commit failed — resolve the hook failure, then re-run."
		exit 1
	fi
	rm -f "$str_backup"
	print_status "success" "Checkpoint recorded in $CHECKPOINTS_FILE."
}

checkout_branch() {
	local str_branch="$1"

	print_status "info" "Checking out '$str_branch'..."
	if ! git checkout "$str_branch"; then
		print_status "error" "Failed to checkout branch '$str_branch'."
		exit 1
	fi
}

merge_into_target() {
	local str_source_branch="$1"
	local str_target="$2"

	print_status "info" "Merging '$str_source_branch' into '$str_target'..."
	# --no-verify bypasses the protect-branch pre-commit hook, which would
	# otherwise block the merge commit landing on the protected default branch.
	# --no-edit accepts the default merge-commit message non-interactively.
	if ! git merge --no-ff --no-edit --no-verify "$str_source_branch"; then
		print_status "error" "Merge failed. Resolve conflicts manually."
		exit 1
	fi

	print_status "success" "Branch '$str_source_branch' merged into '$str_target'."
}

delete_branch() {
	local str_branch="$1"

	print_status "info" "Deleting branch '$str_branch'..."
	if ! git branch -d "$str_branch"; then
		print_status "error" "Merge succeeded, but deleting branch '$str_branch' failed."
		exit 1
	fi

	print_status "success" "Branch '$str_branch' deleted."
}

main() {
	local str_current_branch
	local str_target_branch
	local str_status

	ensure_git_repo

	str_target_branch="$(resolve_default_branch "${1:-}")"
	print_status "config" "Default branch resolved to '$str_target_branch'."
	ensure_target_branch_exists "$str_target_branch"

	str_current_branch="$(get_current_branch)"

	if [[ "$str_current_branch" == "$str_target_branch" ]]; then
		print_status "error" "You are already on '$str_target_branch'. Checkout a feature branch first."
		exit 1
	fi

	str_status="$(get_git_status_porcelain)"

	if has_uncommitted_changes "$str_status"; then
		print_status "error" "There are uncommitted tracked changes. Commit or stash them before merging."
		exit 1
	fi

	if has_untracked_files "$str_status"; then
		print_status "error" "There are untracked files. Commit, remove, or ignore them before merging."
		exit 1
	fi

	print_status "success" "Working tree is clean on branch '$str_current_branch'."

	record_checkpoint "$str_current_branch" "$str_target_branch"

	checkout_branch "$str_target_branch"
	merge_into_target "$str_current_branch" "$str_target_branch"
	delete_branch "$str_current_branch"

	print_status "success" "Done: '$str_current_branch' was merged into '$str_target_branch' and deleted."
}

main "$@"

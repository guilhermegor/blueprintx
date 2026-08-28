#!/bin/bash
# Close the linked issues (and delete the head branches) of MERGED PRs.
#
# Extracted from the `pr-reconcile.yaml` workflow's inline `run:` block (blueprintx#255) so the
# logic has ONE implementation invoked from every workflow that ships it, the same shape as
# `check_review_threads.py` and `rerun_stale_gate_runs.sh`. It was inline-only until then, so no
# generated project ever ran a version separate from the one that shipped it — a fork was never
# even possible, which is a reason to extract it, not a reason it was fine as-is.
#
# WHY THIS EXISTS — see the workflow file for the full "why" (native auto-merge by a bot merges a
# PR but neither closes its linked issues nor fires delete_branch_on_merge). This script is the
# mechanism; the workflow supplies triggers, permissions and the scheduled backstop.
#
# Consumes from the environment:
#   GH_TOKEN, GH_REPO   — required, set by the calling workflow.
#   EVENT_PR            — a single PR number to reconcile (the fast, event-driven path).
#   SWEEP_LIMIT         — how many recently-merged PRs to sweep when EVENT_PR is unset
#                          (the scheduled/dispatch backstop path). Defaults to 30.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Close every linked issue that is still OPEN. An already-closed issue is a no-op, and a PR with
# no linked issues iterates zero times.
close_linked_issues() {
	local str_pr="$1"
	local str_issue str_state

	for str_issue in $(gh pr view "$str_pr" --json closingIssuesReferences \
		--jq '.closingIssuesReferences[].number' 2>/dev/null || true); do
		str_state="$(gh issue view "$str_issue" --json state --jq .state 2>/dev/null || echo "")"
		if [[ "$str_state" == "OPEN" ]]; then
			print_status "info" "PR #$str_pr -> closing issue #$str_issue"
			gh issue close "$str_issue" --reason completed \
				--comment "Closed by #$str_pr (reconciled: a bot-performed merge does not close linked issues)." \
				|| echo "::warning::could not close issue #$str_issue"
		fi
	done
}

# Second casualty of the same root cause: delete_branch_on_merge does not fire for a bot merge
# either. Only ever deletes a same-repo branch — a fork's head branch is not ours to delete.
delete_head_branch() {
	local str_pr="$1"
	local str_ref str_is_fork

	str_ref="$(gh pr view "$str_pr" --json headRefName --jq .headRefName 2>/dev/null || echo "")"
	str_is_fork="$(gh pr view "$str_pr" --json isCrossRepository --jq .isCrossRepository 2>/dev/null || echo "true")"

	if [[ -n "$str_ref" && "$str_is_fork" == "false" ]]; then
		# An already-deleted branch is a no-op, not an error.
		if gh api -X DELETE "repos/$GH_REPO/git/refs/heads/$str_ref" >/dev/null 2>&1; then
			print_status "success" "PR #$str_pr -> deleted branch $str_ref"
		fi
	fi
}

# Only act on a MERGED pr; a closed-unmerged PR must not close its linked issues.
reconcile_pr() {
	local str_pr="$1"
	local str_merged

	str_merged="$(gh pr view "$str_pr" --json merged --jq .merged 2>/dev/null || echo "false")"
	[[ "$str_merged" == "true" ]] || return 0

	close_linked_issues "$str_pr"
	delete_head_branch "$str_pr"
}

main() {
	local str_pr

	if [[ -n "${EVENT_PR:-}" ]]; then
		reconcile_pr "$EVENT_PR"
		return 0
	fi

	# Bounded sweep: walk the most recently merged PRs and reconcile anything the event path
	# missed (the scheduled backstop — see the workflow file for why this half is load-bearing).
	for str_pr in $(gh pr list --state merged --limit "${SWEEP_LIMIT:-30}" --json number --jq '.[].number'); do
		reconcile_pr "$str_pr"
	done
}

main "$@"

#!/bin/bash
# Re-run the STALE FAILED runs of this workflow that still poison the merge rollup.
#
# The review-thread gate re-triggers on `pull_request`, `pull_request_review` and
# `pull_request_review_comment` — deliberately, because a verdict computed at push time goes
# stale the moment a review lands. But each trigger creates a NEW check run rather than
# updating the previous one, and branch protection reads the AGGREGATE. So the push-time run,
# which failed correctly (the threads really were unanswered at that moment), keeps the PR
# `mergeStateStatus=BLOCKED` no matter how many later runs pass.
#
# Measured three times, and the count SCALES with how many threads you answer, because each
# reply re-fires the gate BEFORE the last thread is resolved:
#   blueprintx#262 -> 1 stale failure   (7 successes after it, still BLOCKED)
#   blueprintx#264 -> 5 stale failures
#   blueprintx#265 -> 7 stale failures
# In every case `gh run rerun <id> --failed` on ONLY the stale failures flipped the PR to
# `CLEAN`/`SUCCESS` with nothing else changed. That is the manual step this script automates.
#
# ⚠️ WHY NOT `concurrency:` — IT WAS TRIED AND IT IS STRICTLY WORSE.
# See the block above `jobs:` in the workflow. `cancel-in-progress: false` still cancels a
# QUEUED run, and a run cancelled before it starts publishes NO check run at all, leaving the
# required context `Expected — Waiting for status to be reported`, which no re-run clears. A
# stale RED is at least clickable; an UNREPORTED context is a deadlock with nothing to click.
#
# ⚠️ WHY THIS EXITS 0 EVEN WHEN IT CANNOT DO ITS JOB — AND WHY THAT IS NOT FAILING OPEN.
# This is a janitor, not a guard. If it fails, the stale run stays red and the PR stays
# BLOCKED — the status quo, still fully visible, hiding nothing. Whereas failing the STEP
# would fail the job, which would deposit one more failed run into the very rollup it came to
# clean. So it reports loudly (a `::warning::` annotation surfaces in the run summary) and
# returns 0.
#
# Consumes GITHUB_REPOSITORY, GITHUB_RUN_ID and HEAD_SHA from the workflow, and needs the
# `actions: write` permission to re-run anything.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Refuse to do anything outside a pull-request run rather than guessing at a subject. An empty
# HEAD_SHA is the ordinary case on a non-PR event, not an error worth colouring red.
preconditions_met() {
	if [[ -z "${GITHUB_REPOSITORY:-}" || -z "${GITHUB_RUN_ID:-}" ]]; then
		print_status "info" "Not inside a GitHub Actions run — nothing to clear."
		return 1
	fi

	if [[ -z "${HEAD_SHA:-}" ]]; then
		print_status "info" "No HEAD_SHA (not a pull-request event) — nothing to clear."
		return 1
	fi

	return 0
}

# Ask the API which workflow the CURRENT run belongs to, rather than matching on a name or a
# filename. The two shipped copies of this gate disagree on both (`review_threads.yml` here,
# `review_threads.yaml` in a generated project), and a name match would silently clean nothing
# the day either is renamed.
resolve_workflow_id() {
	gh api "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" --jq '.workflow_id'
}

# Only runs of THIS workflow, at THIS head, that ended in failure. Scoping by head_sha is what
# keeps the cleanup from touching an older commit's genuine failures.
list_stale_failed_runs() {
	local str_workflow_id="$1"

	gh api --paginate --method GET "repos/$GITHUB_REPOSITORY/actions/runs" \
		-f "head_sha=$HEAD_SHA" \
		-f "status=failure" \
		--jq ".workflow_runs[] | select(.workflow_id == $str_workflow_id) | .id"
}

rerun_one() {
	local str_run_id="$1"

	if gh api --method POST \
		"repos/$GITHUB_REPOSITORY/actions/runs/$str_run_id/rerun-failed-jobs" >/dev/null 2>&1; then
		print_status "success" "Re-ran stale failed run $str_run_id."
		return 0
	fi

	echo "::warning::Could not re-run stale failed run $str_run_id — the PR stays BLOCKED until it is re-run by hand. Check the 'actions: write' permission."
	print_status "warning" "Could not re-run stale failed run $str_run_id (needs 'actions: write')."
	return 0
}

# ⚠️ SKIPPING $GITHUB_RUN_ID IS THE LOOP GUARD, NOT A TIDINESS DETAIL. This step only runs on a
# SUCCESSFUL run, so re-running ourselves would be re-running a green run forever.
clear_stale_runs() {
	local str_workflow_id="$1"
	local -a list_run_ids=()
	local str_run_id
	local str_discovered
	local int_cleared=0

	# ⚠️ NOT `mapfile < <(producer)` — that form DISCARDS the producer's exit status and reports
	# only mapfile's own. A failing `gh api` would then yield an EMPTY list, and this function
	# would announce "the rollup is already clean" over a query that never ran. Same trap
	# `bin/lint_docker.sh` documents at its own discovery call.
	if ! str_discovered="$(list_stale_failed_runs "$str_workflow_id")"; then
		echo "::warning::Could not list this workflow's runs at $HEAD_SHA — no stale run was cleared."
		print_status "warning" "Could not list runs at $HEAD_SHA — nothing cleared."
		return 0
	fi

	mapfile -t list_run_ids <<<"$str_discovered"

	for str_run_id in "${list_run_ids[@]}"; do
		if [[ -n "$str_run_id" && "$str_run_id" != "$GITHUB_RUN_ID" ]]; then
			rerun_one "$str_run_id"
			int_cleared=$((int_cleared + 1))
		fi
	done

	if [[ "$int_cleared" -eq 0 ]]; then
		print_status "info" "No stale failed run at $HEAD_SHA — the rollup is already clean."
		return 0
	fi

	print_status "success" "Re-ran $int_cleared stale failed run(s) at $HEAD_SHA."
	return 0
}

main() {
	if ! preconditions_met; then
		return 0
	fi

	local str_workflow_id
	if ! str_workflow_id="$(resolve_workflow_id)"; then
		echo "::warning::Could not resolve this run's workflow id — no stale run was cleared."
		print_status "warning" "Could not resolve this run's workflow id — nothing cleared."
		return 0
	fi

	clear_stale_runs "$str_workflow_id"
	return 0
}

main "$@"

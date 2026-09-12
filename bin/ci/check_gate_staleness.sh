#!/usr/bin/env bash
# check_gate_staleness.sh — pair "behind base" with "gate file changed since merge-base"
# (blueprintx#368).
#
# A PR runs every gate script from ITS OWN checkout. A branch behind `main` therefore runs an
# OLD copy of a gate (e.g. `check_review_threads.py`), and can fail — or wrongly pass — for a
# reason that has nothing to do with the PR's own diff. Before this script, "behind base" and
# "gate failing" were reported separately, so a PR failing BECAUSE it is behind was
# indistinguishable from one failing on its own merits (blueprintx#368's "loop gap").
#
# ⚠️ THIS IS A REPORT, NOT A FIX — DELIBERATELY. `gh pr update-branch` fixes the gate version
# but moves the head commit, which can flip an already-clean review to SUPERSEDED (a review is
# pinned to the commit it was written against and nothing re-pins it). Measured directly on
# #444: merging main into it moved the head and the gate flipped from OK to SUPERSEDED in one
# step. Spending a review-quota unit on any one PR is a judgment call — which PR is "otherwise
# ready" for that spend — so it is left to a human. This script only automates the DATA half:
# is the PR behind, AND does that gap include a gate file it is judged by.
set -euo pipefail

# Gate-relevant paths: changing one of these on `main` after a PR's merge-base means the PR's
# own checkout is judged by an OLD copy of it. Kept in sync by hand with the gate family this
# repo runs — see CLAUDE.md's gate table for the full list and why each lives where it does.
declare -a GATE_PATHS=(
	"bin/ci"
	"templates/common/bin/check_review_threads.py"
	".github/workflows/review_threads.yml"
	".github/workflows/scaffold_checks.yml"
)

git fetch origin main --quiet

int_stale=0
int_examined=0

while IFS=$'\t' read -r str_number str_head_ref; do
	[ -n "$str_number" ] || continue
	int_examined=$((int_examined + 1))

	if ! git fetch origin "$str_head_ref" --quiet 2>/dev/null; then
		echo "::warning::PR #${str_number} (${str_head_ref}): could not fetch — skipping"
		continue
	fi

	str_merge_base=$(git merge-base FETCH_HEAD origin/main)
	int_behind=$(git rev-list --count "FETCH_HEAD..origin/main")
	str_changed=$(git diff --name-only "$str_merge_base" origin/main -- "${GATE_PATHS[@]}")

	if [ "$int_behind" -gt 0 ] && [ -n "$str_changed" ]; then
		int_stale=$((int_stale + 1))
		echo "::warning::PR #${str_number} (${str_head_ref}) is ${int_behind} commit(s) behind" \
			"main AND main changed a gate file it is judged by since merge-base:"
		while IFS= read -r str_line; do
			echo "    ${str_line}"
		done <<<"$str_changed"
	elif [ "$int_behind" -gt 0 ]; then
		echo "PR #${str_number} (${str_head_ref}): ${int_behind} commit(s) behind main," \
			"no gate files changed — not stale."
	else
		echo "PR #${str_number} (${str_head_ref}): up to date with main."
	fi
done < <(gh pr list --state open --json number,headRefName -q '.[] | [.number, .headRefName] | @tsv')

echo
echo "${int_stale} of ${int_examined} open PR(s) behind base AND judged by a stale gate."
echo "This is a report, not an auto-fix — see the file header for why update-branch stays a"
echo "human decision."

# Advisory only: never fail the run. A red required check here would pressure someone into
# exactly the mass update-branch the issue measured as a review-quota burst vector.
exit 0

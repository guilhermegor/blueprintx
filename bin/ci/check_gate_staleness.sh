#!/usr/bin/env bash
set -euo pipefail

declare -a GATE_PATHS=(
	"bin/ci"
	"templates/common/bin/check_review_threads.py"
	".github/workflows/review_threads.yml"
	".github/workflows/scaffold_checks.yml"
)

if ! git fetch origin main --quiet; then
	echo "::warning::could not fetch origin/main — skipping staleness check"
	exit 0
fi

int_stale=0
int_examined=0

while IFS=$'\t' read -r str_number str_head_ref; do
	[ -n "$str_number" ] || continue
	int_examined=$((int_examined + 1))

	if ! git fetch origin "refs/pull/${str_number}/head" --quiet 2>/dev/null; then
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
done < <(gh pr list --state open --limit 1000 --json number,headRefName -q '.[] | [.number, .headRefName] | @tsv')

echo
echo "${int_stale} of ${int_examined} open PR(s) behind base AND judged by a stale gate."
echo "This is a report, not an auto-fix — see the file header for why update-branch stays a"
echo "human decision."

exit 0

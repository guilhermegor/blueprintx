#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS="$REPO_ROOT/templates/python-common/.github/workflows"
int_failures=0

check() {
	if "${@:2}"; then
		echo "ok: $1"
	else
		echo "FAIL: $1"
		int_failures=$((int_failures + 1))
	fi
}

has_line() { grep -qE "$2" "$WORKFLOWS/$1"; }
lacks_line() { ! grep -qE "$2" "$WORKFLOWS/$1"; }
backfill_job() { sed -n '/^  backfill:/,$p' "$WORKFLOWS/pr-gate.yml"; }
backfill_polls_once() { backfill_job | grep -qE '^ +GATE_MAX_POLLS: "1"$'; }

check "trigger runs in the base context, so a fork PR still gets the PAT" \
	has_line coderabbit-trigger.yml '^  pull_request_target:$'
check "trigger keeps no plain pull_request event" \
	lacks_line coderabbit-trigger.yml '^  pull_request:$'
check "trigger never checks out PR code" \
	lacks_line coderabbit-trigger.yml 'actions/checkout'
check "trigger never reads a PR-controlled head field" \
	lacks_line coderabbit-trigger.yml 'pull_request\.head|head_ref'
check "backfill reads each PR once instead of sleeping on it inside one job timeout" \
	backfill_polls_once

GATES=(
	"$REPO_ROOT/.github/workflows/review_threads.yml"
	"$REPO_ROOT/templates/python-common/.github/workflows/review-threads.yml"
	"$REPO_ROOT/templates/ts-common/.github/workflows/review-threads.yml"
)

gate_has() { grep -qE "$2" "$1"; }
gate_lacks() { ! grep -qE "$2" "$1"; }
gate_job_name_differs() { ! grep -qE '^    name: Review threads answered$' "$1"; }
gate_posts_on_always() { grep -qE '^        if: always\(\)$' "$1" && grep -q 'check-runs' "$1" && grep -q 'conclusion="\$str_conclusion"' "$1"; }
gate_checkout_is_base() { grep -qE 'ref: \$\{\{ github\.event\.repository\.default_branch \}\}$' "$1"; }

for gate in "${GATES[@]}"; do
	label="${gate#"$REPO_ROOT"/}"
	check "$label runs from the base via pull_request_target" gate_has "$gate" '^  pull_request_target:$'
	check "$label keeps no plain pull_request event" gate_lacks "$gate" '^  pull_request:$'
	check "$label re-runs on edited" gate_has "$gate" 'types: \[opened, synchronize, reopened, edited\]'
	check "$label checks out the base, never the PR head" gate_checkout_is_base "$gate"
	check "$label never reads a PR head ref" gate_lacks "$gate" 'pull_request\.head\.(ref|sha)|head_ref|refs/pull'
	check "$label holds checks: write" gate_has "$gate" '^  checks: write$'
	check "$label names its job apart from the required context" gate_job_name_differs "$gate"
	check "$label posts the result as a check-run even after a failure" gate_posts_on_always "$gate"
done

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

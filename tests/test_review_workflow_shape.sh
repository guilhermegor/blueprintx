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

repo_workflows="$REPO_ROOT/.github/workflows"
ruff_installs_pinned() {
	local installs
	installs="$(grep -rnE 'pipx install ruff([^-[:alnum:]_]|$)' "$repo_workflows")" || return 1
	! grep -vE 'pipx install ruff==[0-9]' <<<"$installs"
}
check "every pipx install ruff under .github/workflows is pinned with ==<version>" \
	ruff_installs_pinned

main_run_never_cancelled() {
	! grep -qE '^ +cancel-in-progress: true$' "$repo_workflows/$1"
}
check "scaffold_checks (push to main) never cancels a run unconditionally" \
	main_run_never_cancelled scaffold_checks.yml

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

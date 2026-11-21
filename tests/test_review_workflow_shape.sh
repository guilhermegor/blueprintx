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

GATE_WF="$REPO_ROOT/.github/workflows/review_threads.yml"
gate_step() {
	local str_files="$1" str_labels="$2" str_dir int_rc
	str_dir=$(mktemp -d)
	awk '/name: Gate files unchanged/{f=1} f&&/^        run: \|/{r=1;next} r&&/^      - /{exit} r' "$GATE_WF" | sed 's/^          //' >"$str_dir/step.sh"
	printf '#!/bin/bash\ncase "$*" in *labels*) printf "%%s\\n" "$FAKE_LABELS";; *) printf "%%s\\n" "$FAKE_FILES";; esac\n' >"$str_dir/gh"
	chmod +x "$str_dir/gh"
	PATH="$str_dir:$PATH" GITHUB_REPOSITORY=o/r PR_NUMBER=1 FAKE_FILES="$str_files" FAKE_LABELS="$str_labels" \
		bash "$str_dir/step.sh" 2>&1
	int_rc=$?
	rm -rf "$str_dir"
	return $int_rc
}
gate_edit="templates/common/bin/check_review_threads.py"
gate_step_passes() { gate_step "$@" >/dev/null; }
gate_step_fails() {
	local str_out
	str_out=$(gate_step "$@")
	[ $? -eq 1 ] && grep -qF "$gate_edit" <<<"$str_out"
}
check "gate edit without the label fails the step" gate_step_fails "$gate_edit" "bug"
check "same gate edit with the label passes" gate_step_passes "$gate_edit" "gate-change-approved"
check "unrelated edit passes without the label" gate_step_passes "README.md" ""
check "review-thread gate runs again when the label changes" \
	grep -qE 'types: \[.*unlabeled' "$GATE_WF"

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

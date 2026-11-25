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

retrigger_job() { sed -n '/^  retrigger:/,/^  backfill:/p' "$WORKFLOWS/pr-gate.yml"; }
retrigger_reruns_failed_gate() { retrigger_job | grep -qE 'gh run rerun'; }
retrigger_may_write_actions() { retrigger_job | grep -qE '^ +actions: write$'; }
retrigger_may_read_prs() { retrigger_job | grep -qE '^ +pull-requests: read$'; }
retrigger_may_read_contents() { retrigger_job | grep -qE '^ +contents: read$'; }
tests_workflow_is_named_run_tests() { grep -qxF 'name: Run Tests' "$WORKFLOWS/tests.yml"; }
retrigger_waits_for_running_gate() { retrigger_job | grep -qE 'status,conclusion' && retrigger_job | grep -q 'sleep '; }

check "gate re-triggers when Run Tests completes, so a slow suite cannot strand it red" \
	has_line pr-gate.yml '^  workflow_run:$'
check "the workflow_run trigger names Run Tests and the gate itself" \
	has_line pr-gate.yml '^    workflows: \["Run Tests", "PR Quality Gate"\]$'
check "the workflow is still named PR Quality Gate, which both re-run jobs match on" \
	has_line pr-gate.yml '^name: PR Quality Gate$'
check "the retrigger job re-runs the failed gate run" \
	retrigger_reruns_failed_gate
check "the retrigger job carries the actions: write it needs" \
	retrigger_may_write_actions
check "the retrigger job can read the PR head on a private repo" \
	retrigger_may_read_prs
check "the retrigger job can list a commit's PRs on a private repo" \
	retrigger_may_read_contents
check "the workflow the trigger names is still called Run Tests" \
	tests_workflow_is_named_run_tests
check "the retrigger job waits out an in-progress gate run" \
	retrigger_waits_for_running_gate
check "the retrigger job never checks out code" \
	bash -c "! sed -n '/^  retrigger:/,/^  backfill:/p' '$WORKFLOWS/pr-gate.yml' | grep -q 'actions/checkout'"
late_rerun_job() { sed -n '/^  late_rerun:/,/^  retrigger:/p' "$WORKFLOWS/pr-gate.yml"; }
late_rerun_count() {
	local str_attempt="$1" str_conclusion="$2" str_dir
	str_dir=$(mktemp -d)
	late_rerun_job | awk '/^        run: \|/{r=1;next} r&&/^  [a-z]/{exit} r' |
		sed 's/^          //' >"$str_dir/step.sh"
	cat >"$str_dir/gh" <<-'EOF'
		#!/bin/bash
		case "$*" in
		"api "*) echo 1 ;;
		"run view "*) echo "$FAKE_ATTEMPT completed $FAKE_CONCLUSION" ;;
		"run list "*) echo "${FAKE_PENDING:-0}" ;;
		"run rerun "*)
			if [ -n "$FAKE_RERUN_ERR" ]; then
				echo "$FAKE_RERUN_ERR" >&2
				exit 1
			fi
			echo "$*" >>"$RERUN_LOG"
			;;
		esac
	EOF
	chmod +x "$str_dir/gh"
	PATH="$str_dir:$PATH" GH_REPO=o/r HEAD_SHA=abc RUN_ID=7 RERUN_LOG="$str_dir/log" \
		FAKE_ATTEMPT="$str_attempt" FAKE_CONCLUSION="$str_conclusion" \
		bash -e "$str_dir/step.sh" >/dev/null 2>&1
	LATE_RC=$?
	{ [ -f "$str_dir/log" ] && wc -l <"$str_dir/log" || echo 0; } | tr -d ' '
	rm -rf "$str_dir"
}
tests_still_running_no_rerun() { [ "$(FAKE_PENDING=1 late_rerun_count 1 failure)" = 0 ]; }
late_failure_rerun_once() { [ "$(late_rerun_count 1 failure)" = 1 ]; }
passing_gate_never_rerun() { [ "$(late_rerun_count 1 success)" = 0 ]; }
rerun_attempt_never_rerun_again() { [ "$(late_rerun_count 2 failure)" = 0 ]; }
late_rerun_rc() {
	local str_dir
	str_dir=$(mktemp -d)
	late_rerun_job | awk '/^        run: \|/{r=1;next} r&&/^  [a-z]/{exit} r' |
		sed 's/^          //' >"$str_dir/step.sh"
	printf '#!/bin/bash\ncase "$*" in\n"api "*) echo 1 ;;\n"run view "*) echo "1 completed failure" ;;\n"run list "*) echo 0 ;;\n"run rerun "*) echo "$FAKE_RERUN_ERR" >&2; exit 1 ;;\nesac\n' >"$str_dir/gh"
	chmod +x "$str_dir/gh"
	PATH="$str_dir:$PATH" GH_REPO=o/r HEAD_SHA=abc RUN_ID=7 bash -e "$str_dir/step.sh" >/dev/null 2>&1
	local int_rc=$?
	rm -rf "$str_dir"
	return $int_rc
}
rerun_already_running_is_tolerated() { FAKE_RERUN_ERR="this workflow is already running" late_rerun_rc; }
rerun_other_error_fails_the_job() { ! FAKE_RERUN_ERR="HTTP 403: Resource not accessible" late_rerun_rc; }
late_rerun_runs_only_on_gate_failure() {
	late_rerun_job | grep -qF "github.event.workflow_run.name == 'PR Quality Gate'" &&
		late_rerun_job | grep -qF "github.event.workflow_run.conclusion == 'failure'"
}
retrigger_runs_only_for_run_tests() {
	retrigger_job | grep -qF "github.event.workflow_run.name == 'Run Tests'"
}
late_rerun_never_waits() { ! late_rerun_job | grep -q 'sleep '; }
late_rerun_may_write_actions() { late_rerun_job | grep -qE '^ +actions: write$'; }
check "a re-run already in flight does not fail the job" rerun_already_running_is_tolerated
check "a re-run refused for any other reason fails the job" rerun_other_error_fails_the_job
check "a gate that fails after the retrigger window gets exactly one re-run" \
	late_failure_rerun_once
check "a gate that failed while Run Tests still runs keeps its retry for retrigger" \
	tests_still_running_no_rerun
check "a passing gate gets no re-run" passing_gate_never_rerun
check "a gate already re-run once is not re-run again" rerun_attempt_never_rerun_again
check "the late re-run job fires only on a failed PR Quality Gate run" \
	late_rerun_runs_only_on_gate_failure
check "the retrigger job fires only for a Run Tests completion, not the gate's own" \
	retrigger_runs_only_for_run_tests
check "the late re-run job holds no runner waiting for the gate" late_rerun_never_waits
check "the late re-run job carries the actions: write it needs" late_rerun_may_write_actions
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
gate_step_fails_on() {
	local str_out
	str_out=$(gate_step "$1" "$3")
	[ $? -eq 1 ] && grep -qF "$2" <<<"$str_out"
}
check "gate edit without the label fails the step" gate_step_fails "$gate_edit" "bug"
check "same gate edit with the label passes" gate_step_passes "$gate_edit" "gate-change-approved"
check "unrelated edit passes without the label" gate_step_passes "README.md" ""
check "roster edit without the label fails the step" gate_step_fails_on ".review-bots.yaml" ".review-bots.yaml" "bug"
check "rename away from a gated path fails the step" gate_step_fails_on \
	"docs/old.py"$'\n'"$gate_edit" "$gate_edit" "bug"
check "near-match label does not approve" gate_step_fails "$gate_edit" "gate-change-approved-x"
check "review-thread gate re-runs when a label is added" \
	grep -qE 'types: \[.*\blabeled\b' "$GATE_WF"
check "review-thread gate re-runs when a label is removed" \
	grep -qE 'types: \[.*unlabeled' "$GATE_WF"

repo_workflows="$REPO_ROOT/.github/workflows"
ruff_installs_pinned() {
	local installs
	installs="$(grep -rnE 'pipx install ruff([^-[:alnum:]_]|$)' "$repo_workflows")" || return 1
	! grep -vE 'pipx install ruff==[0-9]' <<<"$installs"
}
check "every pipx install ruff under .github/workflows is pinned with ==<version>" \
	ruff_installs_pinned

main_run_never_cancelled() {
	[ -f "$repo_workflows/$1" ] || return 1
	! grep -qE "^ +cancel-in-progress: *(true|'true'|\"true\"|\\$\\{\\{ *true *\\}\\})( *#.*)?$" "$repo_workflows/$1"
}
check "scaffold_checks (push to main) never cancels a run unconditionally" \
	main_run_never_cancelled scaffold_checks.yml

push_runs_get_own_group() {
	grep -qE '^ +group: .*github\.sha' "$repo_workflows/$1"
}
check "scaffold_checks push runs are keyed by sha, so none replaces a pending main run" \
	push_runs_get_own_group scaffold_checks.yml

every_suite_wired() {
	local f b int_missing=0
	for f in "$REPO_ROOT"/tests/test_*.sh; do
		b="$(basename "$f")"
		grep -rqE "^[^#]*bash tests/${b//./\\.}([^[:alnum:]_.-]|$)" "$repo_workflows" "$REPO_ROOT/.pre-commit-config.yaml" || {
			echo "unwired: $b"
			int_missing=1
		}
	done
	[ "$int_missing" -eq 0 ]
}
check "every tests/test_*.sh is referenced by a workflow or the pre-commit config" \
	every_suite_wired

[ "$int_failures" -eq 0 ] && echo "all passed" || {
	echo "$int_failures failure(s)"
	exit 1
}

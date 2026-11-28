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
gate_posts_unless_cancelled() { grep -qE "^        if: \"!cancelled\(\) && steps\.head\.outputs\.sha != ''\"$" "$1" && grep -q 'check-runs' "$1" && grep -q 'conclusion="\$str_conclusion"' "$1"; }
gate_serialized_per_pr() { grep -qE '^  cancel-in-progress: true$' "$1" && grep -qE '^  group: review-gate-' "$1"; }
gate_checkout_is_base() {
	awk '
		function flush() { if (co) { n++; if (!ok) bad = 1 } co = 0; ok = 0 }
		/^ +- / { flush() }
		/uses: actions\/checkout@/ { co = 1 }
		co && /^ +ref: / { if ($0 ~ BASE) ok = 1; else bad = 1 }
		END { flush(); exit (bad || n < 1) }
	' BASE='^ +ref: \\$\\{\\{ github\\.event\\.repository\\.default_branch \\}\\}$' "$1"
}
gate_run_blocks_clean() {
	awk '
		/^ +(- )?run: [|>]/ { inrun = 1; match($0, /^ +(- )?/); ind = RLENGTH; next }
		/^ +(- )?run: / { if ($0 ~ BAD) bad = 1; inrun = 0; next }
		inrun { match($0, /^ */); if (RLENGTH < ind && $0 !~ /^ *$/) inrun = 0; else if ($0 ~ BAD) bad = 1 }
		END { exit bad }
	' BAD='\\$\\{\\{[^}]*(comment\\.body|issue\\.(title|body)|pull_request\\.(title|body)|review\\.body|head_ref|head\\.ref|label\\.name)' "$1"
}
gate_secrets_token_only() { ! awk '/^  publish-app-check:/{f=1} !f' "$1" | grep -E 'secrets\.' | grep -qvE 'secrets\.GITHUB_TOKEN( |$)'; }
gate_run_blocks_reject_injection() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	printf 'jobs:\n  j:\n    steps:\n      - name: x\n        run: |\n          echo "${{ github.event.comment.body }}"\n' >"$str_dir/bad.yml"
	printf 'jobs:\n  j:\n    steps:\n      - name: x\n        env:\n          B: ${{ github.event.comment.body }}\n        run: echo "$B"\n' >"$str_dir/ok.yml"
	printf 'jobs:\n  j:\n    steps:\n      - run: echo "${{ github.event.issue.title }}"\n' >"$str_dir/dash1.yml"
	printf 'jobs:\n  j:\n    steps:\n      - run: |\n          echo "${{ github.event.review.body }}"\n' >"$str_dir/dash2.yml"
	gate_run_blocks_clean "$str_dir/bad.yml" && rc=1
	gate_run_blocks_clean "$str_dir/dash1.yml" && rc=1
	gate_run_blocks_clean "$str_dir/dash2.yml" && rc=1
	gate_run_blocks_clean "$str_dir/ok.yml" || rc=1
	rm -rf "$str_dir"
	return $rc
}
gate_checkout_rejects_second_head() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	{
		printf '      - uses: actions/checkout@x\n        with:\n          ref: ${{ github.event.repository.default_branch }}\n'
		printf "      - uses: actions/checkout@x\n        with:\n          ref: \${{ github.event.pull_request['head']['sha'] }}\n"
	} >"$str_dir/two.yml"
	gate_checkout_is_base "$str_dir/two.yml" && rc=1
	printf "      - uses: actions/checkout@x\n        with:\n          ref: \${{ github.event['pull_request']['head']['sha'] }}\n      - run: echo ok\n        env:\n          ref: \${{ github.event.repository.default_branch }}\n" >"$str_dir/stray.yml"
	gate_checkout_is_base "$str_dir/stray.yml" && rc=1
	printf '      - uses: actions/checkout@x\n' >"$str_dir/noref.yml"
	gate_checkout_is_base "$str_dir/noref.yml" && rc=1
	rm -rf "$str_dir"
	return $rc
}

gate_step_gets_evaluated_head() {
	awk '
		/^ +id: gate$/ { ing = 1; next }
		ing && /^      - / { ing = 0 }
		ing && $0 ~ WANT { ok = 1 }
		END { exit !ok }
	' WANT='^ +EVALUATED_HEAD: \\$\\{\\{ steps\\.head\\.outputs\\.sha \\}\\}$' "$1"
}
gate_step_evaluated_head_rejects_misplacement() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	printf '      - name: g\n        id: gate\n        env:\n          EVALUATED_HEAD: ${{ steps.head.outputs.sha }}\n        run: x\n' >"$str_dir/ok.yml"
	printf '      - name: g\n        id: gate\n        env:\n          A: b\n        run: x\n      - name: post\n        env:\n          EVALUATED_HEAD: ${{ steps.head.outputs.sha }}\n' >"$str_dir/post_only.yml"
	gate_step_gets_evaluated_head "$str_dir/ok.yml" || rc=1
	gate_step_gets_evaluated_head "$str_dir/post_only.yml" && rc=1
	rm -rf "$str_dir"
	return $rc
}
gate_secrets_reject_other() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	printf '        env:\n          T: ${{ secrets.GITHUB_TOKEN }}\n' >"$str_dir/ok.yml"
	printf '        env:\n          T: ${{ secrets.PAT_TOKEN }}\n' >"$str_dir/bad.yml"
	gate_secrets_token_only "$str_dir/ok.yml" || rc=1
	gate_secrets_token_only "$str_dir/bad.yml" && rc=1
	rm -rf "$str_dir"
	return $rc
}
check "run: injection check rejects bad fixtures and passes the env: fixture" gate_run_blocks_reject_injection
check "checkout check rejects a second PR-head checkout and a stray base ref" gate_checkout_rejects_second_head
check "secrets check rejects any secret other than GITHUB_TOKEN" gate_secrets_reject_other
checker_records_head() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	CHECKED_HEAD_FILE="$str_dir/h" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/templates/common/bin')
import check_review_threads as m
m._record_evaluated_head({'headRefOid': 'abc123'})" || rc=1
	[ "$(cat "$str_dir/h" 2>/dev/null)" = abc123 ] || rc=1
	rm -rf "$str_dir"
	return $rc
}
check "checker writes the headRefOid it evaluated to CHECKED_HEAD_FILE" checker_records_head
checker_records_head_on_opt_out() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	CHECKED_HEAD_FILE="$str_dir/h" EVALUATED_HEAD=def456 python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/templates/common/bin')
import check_review_threads as m
m.roster_opted_out = lambda p: True
m.base_opted_out = lambda r, str_number: True
_, int_exit = m._roster_or_verdict(False, str_repo_full='o/r', str_number='1')
sys.exit(0 if int_exit == 0 else 1)" >/dev/null || rc=1
	[ "$(cat "$str_dir/h" 2>/dev/null)" = def456 ] || rc=1
	rm -rf "$str_dir"
	return $rc
}
checker_survives_unwritable_head_file() {
	CHECKED_HEAD_FILE=/nonexistent-dir/h python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/templates/common/bin')
import check_review_threads as m
m._record_evaluated_head({'headRefOid': 'abc123'})" 2>/dev/null
}
check "an unwritable CHECKED_HEAD_FILE is reported, not raised" checker_survives_unwritable_head_file
checker_records_head_on_a_clean_pass() {
	local str_dir rc=0
	str_dir=$(mktemp -d)
	CHECKED_HEAD_FILE="$str_dir/h" GITHUB_REPOSITORY=o/r PR_NUMBER=1 python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/templates/common/bin')
import check_review_threads as m
m._roster_or_verdict = lambda *a, **k: ({'bot': {}}, None)
m.reviewer_logins = lambda r: {'bot'}
m._fetch_current_pr = lambda *a, **k: {'headRefOid': 'cafe01', 'reviewThreads': {'nodes': []}}
m._missing_review = lambda *a, **k: ('', '')
m._unanswered_bodies = lambda *a, **k: []
sys.exit(m._check_pull_request(False))" >/dev/null || rc=1
	[ "$(cat "$str_dir/h" 2>/dev/null)" = cafe01 ] || rc=1
	rm -rf "$str_dir"
	return $rc
}
check "a passing run that finds no threads still records the head it evaluated" checker_records_head_on_a_clean_pass
check "gate step EVALUATED_HEAD check rejects a head given only to the reporting step" gate_step_evaluated_head_rejects_misplacement
check "a base-backed opt-out still writes the head read at start to CHECKED_HEAD_FILE" checker_records_head_on_opt_out
for gate in "${GATES[@]}"; do
	label="${gate#"$REPO_ROOT"/}"
	check "$label runs from the base via pull_request_target" gate_has "$gate" '^  pull_request_target:$'
	check "$label keeps no plain pull_request event" gate_lacks "$gate" '^  pull_request:$'
	check "$label re-runs on edited" gate_has "$gate" 'types: \[opened, synchronize, reopened, edited'
	check "$label checks out the base, never the PR head" gate_checkout_is_base "$gate"
	check "$label never reads a PR head ref" gate_lacks "$gate" 'pull_request\.head\.(ref|sha)|pull_request\[.head|head_ref|refs/pull'
	check "$label holds checks: write" gate_has "$gate" '^  checks: write$'
	check "$label keeps actions: read for the pusher lookup" gate_has "$gate" '^  actions: read$'
	check "$label names its job apart from the required context" gate_job_name_differs "$gate"
	check "$label posts the result as a check-run even after a failure, not after a cancel" gate_posts_unless_cancelled "$gate"
	check "$label serializes runs per PR" gate_serialized_per_pr "$gate"
	check "$label interpolates no author-controlled event field into a run: block" gate_run_blocks_clean "$gate"
	check "$label uses no secret except GITHUB_TOKEN" gate_secrets_token_only "$gate"
	check "$label posts success only when the checker's head equals the head read at start" gate_has "$gate" '"\$\(cat "\$CHECKED_HEAD_FILE"[^)]*\)" != "\$EVALUATED_HEAD"'
	check "$label hands the head read at start to the gate step" gate_step_gets_evaluated_head "$gate"
	check "$label publishes against the head read before the gate ran" gate_has "$gate" 'head_sha="\$EVALUATED_HEAD"'
done
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
	if [ "$LATE_RC" -ne 0 ]; then echo "step-exit-$LATE_RC"; else
		{ [ -f "$str_dir/log" ] && wc -l <"$str_dir/log" || echo 0; } | tr -d ' '
	fi
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

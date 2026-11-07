#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/templates/common/bin/delete_closed_pr_branch.sh"
str_wf="$REPO_ROOT/templates/common/.github/workflows/delete-closed-pr-branch.yml"

int_failures=0

check() {
	if [[ "$2" -eq 0 ]]; then
		echo "ok   - $1"
		return 0
	fi
	echo "FAIL - $1"
	int_failures=$((int_failures + 1))
}

for str_guard in 'merged == false' 'head.repo.full_name == github.repository' \
	'head.ref != github.event.repository.default_branch' \
	'head.ref != github.event.pull_request.base.ref'; do
	grep -qF "$str_guard" "$str_wf"
	check "workflow guard present: $str_guard" "$?"
done

str_bin="$(mktemp -d)"
trap 'rm -rf "$str_bin"' EXIT
cat >"$str_bin/gh" <<'STUB'
#!/usr/bin/env bash
echo "$*" >>"$STUB_LOG"
case "$*" in
	*"-X DELETE"*)
		case "$STUB_DELETE" in
			422) echo "Reference does not exist (HTTP 422)" >&2; exit 1 ;;
			ruleset) echo "Repository rule violations found (HTTP 422)" >&2; exit 1 ;;
			500) echo "boom (HTTP 500)" >&2; exit 1 ;;
			*) exit 0 ;;
		esac ;;
	*"/branches/"*)
		case "$STUB_PROTECTED" in
			true | false) echo "$STUB_PROTECTED" ;;
			404) echo "Not Found (HTTP 404)" >&2; exit 1 ;;
			*) echo "boom (HTTP 500)" >&2; exit 1 ;;
		esac ;;
	*)
		case "$STUB_TIP" in
			404) echo "Not Found (HTTP 404)" >&2; exit 1 ;;
			*) echo "$STUB_TIP" ;;
		esac ;;
esac
STUB
chmod +x "$str_bin/gh"

run_script() {
	STUB_LOG="$str_bin/log"
	: >"$STUB_LOG"
	: >"$str_bin/summary"
	PATH="$str_bin:$PATH" STUB_LOG="$STUB_LOG" GITHUB_STEP_SUMMARY="$str_bin/summary" \
		STUB_PROTECTED="${STUB_PROTECTED:-false}" STUB_TIP="${STUB_TIP:-abc}" STUB_DELETE="${STUB_DELETE:-ok}" \
		BRANCH="${BRANCH:-fix/12-x}" BASE_REF="${BASE_REF:-main}" HEAD_SHA="abc" PR="7" GH_REPO="o/r" \
		bash "$SCRIPT" >/dev/null 2>&1
	int_status=$?
	str_log=$(<"$STUB_LOG")
	str_summary=$(<"$str_bin/summary")
}

deleted() { [[ "$str_log" == *"-X DELETE"* ]]; }
in_summary() { [[ "$str_summary" == *"$1"* ]]; }

run_script
deleted
check "a short-lived unprotected branch is deleted" "$?"
in_summary '`fix/12-x` at `abc`'
check "the summary names the ref and the sha" "$?"

BRANCH="develop" run_script
check "a long-lived name is never deleted" "$(deleted && echo 1 || echo 0)"
in_summary "short-lived"
check "a skipped name says why in the summary" "$?"

BRANCH="release/2026" run_script
check "release/<number> is never deleted" "$(deleted && echo 1 || echo 0)"

BRANCH="release/1-rc" run_script
check "release/<N>-<slug> is never deleted" "$(deleted && echo 1 || echo 0)"

BRANCH="fix/12-x" BASE_REF="fix/12-x" run_script
check "the PR's own base ref is never deleted" "$(deleted && echo 1 || echo 0)"
in_summary "base branch"
check "a base-ref skip says why in the summary" "$?"

STUB_PROTECTED=true run_script
check "a protected branch is never deleted" "$(deleted && echo 1 || echo 0)"
in_summary "protected"
check "a protected skip says why in the summary" "$?"

STUB_PROTECTED=500 run_script
check "an unreadable protection state fails closed" "$(deleted && echo 1 || echo 0)"
check "an unreadable protection state does not fail the job" "$((int_status != 0))"

STUB_TIP=zzz run_script
check "a branch whose tip moved is kept" "$(deleted && echo 1 || echo 0)"

STUB_TIP=404 run_script
check "an already-deleted ref is a green no-op" "$(deleted && echo 1 || echo $((int_status != 0)))"

STUB_DELETE=422 run_script
check "a 422 on delete is success" "$((int_status != 0))"

STUB_DELETE=ruleset run_script
check "a ruleset refusal is not reported as already gone" "$(in_summary 'already gone' && echo 1 || echo 0)"
in_summary "refused the deletion"
check "a ruleset refusal is named in the summary" "$?"

BRANCH='fix/12-x#y' run_script
check "a name unsafe in an API path is never deleted" "$(deleted && echo 1 || echo 0)"

STUB_PROTECTED=404 run_script
deleted
check "a 404 protection read proceeds to the tip check and deletes" "$?"

STUB_DELETE=500 run_script
check "a 500 on delete fails the job" "$((int_status == 0))"

if ((int_failures > 0)); then
	echo "$int_failures failure(s)"
	exit 1
fi
echo "all passed"

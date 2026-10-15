#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/bin/ci/check_required_checks_sync.py"
str_tmp="$(mktemp -d)"
trap 'rm -rf "$str_tmp"' EXIT
int_failures=0

fixture() {
	rm -rf "${str_tmp:?}/wf" && mkdir -p "$str_tmp/wf"
	cat >"$str_tmp/wf/a.yml" <<'EOF'
name: a
on: pull_request
jobs:
  lint:
    name: Lint gate
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
  draft-only:
    name: Draft only
    if: github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
  dependent:
    name: Dependent gate
    needs: draft-only
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
EOF
	cat >"$str_tmp/wf/b.yml" <<'EOF'
name: b
on:
  pull_request:
    branches: [main]
jobs:
  filtered:
    name: Filtered gate
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
EOF
	printf 'external|App check|emitted by an app\n' >"$str_tmp/policy.txt"
	expected '"Lint gate", "App check"' ''
}

expected() {
	printf '{"classic": [%s], "ruleset": [%s]}' "$1" "$2" >"$str_tmp/exp.json"
}

run_gate() {
	python3 -I "$GATE" --workflows "$str_tmp/wf" --policy "$str_tmp/policy.txt" \
		--expected "$str_tmp/exp.json" "$@" 2>&1
}

expect() {
	local str_out int_rc=0
	str_out="$(run_gate)" || int_rc=$?
	check "$1" "$int_rc" "$2" "$3" "$str_out"
}

check() {
	if [ "$2" -ne "$3" ] || ! grep -qF -- "$4" <<<"$5"; then
		echo "FAIL: $1 (exit $2, wanted $3, needle '$4')"
		echo "$5"
		int_failures=$((int_failures + 1))
	else
		echo "ok: $1"
	fi
}

fixture
expect "in sync passes" 0 "findings=0"

expected '"Lint gate", "App check", "Ghost job"' ''
expect "required name no job emits fails" 1 "Ghost job"

expected '"Lint gate", "App check"' '"Filtered gate"'
expect "ruleset name behind a branch filter fails" 1 "Filtered gate"

expected '"Lint gate", "App check", "Draft only"' ''
expect "required name behind a job if: fails" 1 "Draft only"

expected '"Lint gate", "App check", "Dependent gate"' ''
expect "required name that needs a conditional job fails" 1 "Dependent gate"

expected '"App check"' ''
expect "unconditional job neither required nor allowlisted fails" 1 "Lint gate"

printf 'optional|Lint gate|measured flaky\n' >>"$str_tmp/policy.txt"
expect "allowlisted optional job passes" 0 "findings=0"

printf 'optional|Gone job|stale\n' >>"$str_tmp/policy.txt"
expect "stale optional entry fails" 1 "Gone job"

fixture
printf 'optional|Lint gate|\n' >>"$str_tmp/policy.txt"
expect "policy line without a reason is rejected" 1 "need"

fixture
printf '{"classic": []}' >"$str_tmp/exp.json"
expect "malformed expected file is rejected" 1 "classic and ruleset"

mkdir -p "$str_tmp/bin"
printf '#!/bin/sh\nexit 1\n' >"$str_tmp/bin/gh"
chmod +x "$str_tmp/bin/gh"
fixture
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" REQUIRED_CHECKS_SYNC_REQUIRED=1 run_gate --live)" || int_rc=$?
check "live read error fails closed in CI" "$int_rc" 1 "failing closed" "$str_out"
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" run_gate --live)" || int_rc=$?
check "live read error skips loudly locally" "$int_rc" 0 "SKIPPED" "$str_out"

printf '%s\n' '#!/bin/sh' 'case "$2" in' \
	'*branches/main/protection) echo "{\"required_status_checks\":{\"contexts\":[\"Lint gate\",\"Extra live\"]}}" ;;' \
	'*rules/branches/main) echo "[{\"type\":\"required_status_checks\",\"parameters\":{\"required_status_checks\":[{\"context\":\"Rule live\"}]}}]" ;;' \
	'*actions/workflows*page=1) echo "{\"workflows\":[{\"path\":\".github/workflows/other.yml\",\"state\":\"active\"}]}" ;;' \
	'*actions/workflows*page=2) echo "{\"workflows\":[{\"path\":\".github/workflows/a.yml\",\"state\":\"${FAKE_STATE:-active}\"}]}" ;;' \
	'*actions/workflows*) echo "{\"workflows\":[]}" ;;' \
	'*) exit 1 ;;' 'esac' >"$str_tmp/bin/gh"
fixture
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" REQUIRED_CHECKS_SYNC_REQUIRED=1 run_gate --live)" || int_rc=$?
check "live drift fails and names both sides" "$int_rc" 1 "not in required-checks.json: Extra live" "$str_out"
check "live ruleset layer comes from the rules in effect on main" "$int_rc" 1 "ruleset: live, not in required-checks.json: Rule live" "$str_out"
check "live drift names the missing live context" "$int_rc" 1 "not live: App check" "$str_out"

fixture
int_rc=0
str_out="$(FAKE_STATE=disabled_manually PATH="$str_tmp/bin:$PATH" REQUIRED_CHECKS_SYNC_REQUIRED=1 run_gate --live)" || int_rc=$?
check "live disabled workflow emitting a required context fails" "$int_rc" 1 "emitted by a.yml, state disabled_manually" "$str_out"

fixture
printf 'name: c\non: pull_request\njobs:\n  t:\n    name: Wrapped true\n    if: ${{ github.event_name == '"'"'pull_request'"'"' }}\n    runs-on: x\n    steps: []\n  c:\n    name: Wrapped cond\n    if: ${{ github.event.pull_request.draft == false }}\n    runs-on: x\n    steps: []\n' >"$str_tmp/wf/c.yml"
expected '"Lint gate", "App check", "Wrapped true"' ''
expect "wrapped always-true if counts as unconditional, wrapped conditional does not" 0 "findings=0"

fixture
printf 'name: d\non: pull_request\njobs:\n  call:\n    uses: ./.github/workflows/x.yml\n' >"$str_tmp/wf/d.yml"
expect "reusable-workflow job fails loudly" 1 "unsupported"

fixture
printf 'name: e\non: pull_request_target\njobs:\n  t:\n    name: Target gate\n    runs-on: x\n    steps: []\n' >"$str_tmp/wf/e.yml"
expect "pull_request_target alone is judged but conditional, so not flagged" 0 "findings=0"

expected '"Lint gate", "App check", "Target gate"' ''
expect "a required name emitted only via pull_request_target fails" 1 "required but no unconditional PR job emits it: Target gate"

fixture
printf 'name: f\non: pull_request\njobs:\n  m:\n    name: Plain\n    runs-on: x\n    strategy:\n      matrix:\n        os: [a, b]\n    steps: []\n' >"$str_tmp/wf/f.yml"
expected '"Lint gate", "App check", "Plain (a)", "Plain (b)"' ''
expect "matrix name without an expression expands to one GitHub-style name (v1, v2) per combination" 0 "findings=0"

fixture
printf 'name: j\non: pull_request\njobs:\n  m:\n    name: Plain\n    runs-on: x\n    strategy:\n      matrix:\n        os: ${{ fromJSON(needs.x.outputs.m) }}\n    steps: []\n' >"$str_tmp/wf/j.yml"
expect "a dynamic-only matrix dimension fails" 1 "non-list matrix dimension"

fixture
printf 'name: j\non: pull_request\njobs:\n  m:\n    name: Plain\n    runs-on: x\n    strategy:\n      matrix:\n        os: ${{ fromJSON(needs.x.outputs.m) }}\n        v: [1, 2]\n    steps: []\n' >"$str_tmp/wf/j.yml"
expect "a dynamic axis next to a list axis fails" 1 "non-list matrix dimension"

fixture
printf 'name: j\non: pull_request\njobs:\n  m:\n    name: Flag\n    runs-on: x\n    strategy:\n      matrix:\n        on: [true, false]\n    steps: []\n' >"$str_tmp/wf/j.yml"
expected '"Lint gate", "App check", "Flag (true)", "Flag (false)"' ''
expect "boolean matrix values render lowercase" 0 "findings=0"

fixture
printf 'name: g\non: pull_request\njobs:\n  m:\n    name: Dyn\n    runs-on: x\n    strategy:\n      matrix: ${{ fromJSON(needs.x.outputs.m) }}\n    steps: []\n' >"$str_tmp/wf/g.yml"
expect "dynamic fromJSON matrix fails with a clear message" 1 "dynamic matrix"

fixture
printf 'name: h\non:\n  pull_request:\n    types: opened\njobs:\n  s:\n    name: Scalar types\n    runs-on: x\n    steps: []\n' >"$str_tmp/wf/h.yml"
expected '"Lint gate", "App check", "Scalar types"' ''
expect "scalar types: is a list, and an incomplete one is conditional" 1 "required but no unconditional PR job emits it: Scalar types"

fixture
printf 'name: h\non:\n  pull_request:\n    types: [opened, reopened, synchronize]\njobs:\n  s:\n    name: Full types\n    runs-on: x\n    steps: []\n' >"$str_tmp/wf/h.yml"
expected '"Lint gate", "App check", "Full types"' ''
expect "a complete types: list stays unconditional" 0 "findings=0"

fixture
printf 'optional|Lint gate|one\noptional|Lint gate|two\n' >>"$str_tmp/policy.txt"
expect "duplicate policy line is rejected" 1 "duplicate or conflicting"

fixture
printf 'optional|App check|clash\n' >>"$str_tmp/policy.txt"
expect "optional/external conflict is rejected" 1 "duplicate or conflicting"

fixture
printf 'name: i\non: push\njobs:\n  m:\n    name: Other\n    runs-on: x\n    strategy:\n      matrix:\n        include: [{a: 1}]\n    steps: []\n' >"$str_tmp/wf/i.yml"
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" REQUIRED_CHECKS_SYNC_REQUIRED=1 run_gate --live)" || int_rc=$?
check "live reports an unrelated include matrix per workflow" "$int_rc" 1 "i.yml: job 'Other'" "$str_out"
check "live keeps checking everything else" "$int_rc" 1 "not live: App check" "$str_out"

list_mode() {
	printf '%s\n' "$1" >"$str_tmp/req.txt"
	int_rc=0
	str_out="$(python3 "$GATE" --workflows "$str_tmp/wf" --required-list "$str_tmp/req.txt" 2>&1)" || int_rc=$?
}

fixture
list_mode "Lint gate"
check "list mode: an unconditional job may be required" "$int_rc" 0 "findings=0" "$str_out"
list_mode "Draft only"
check "list mode: a job with an if: cannot be required" "$int_rc" 1 "no unconditional PR job emits it: Draft only" "$str_out"
list_mode "Dependent gate"
check "list mode: a job needing a conditional job cannot be required" "$int_rc" 1 "Dependent gate" "$str_out"
list_mode "Filtered gate"
check "list mode: a branch-filtered job cannot be required" "$int_rc" 1 "Filtered gate" "$str_out"
for str_tier in python-common ts-common bash-cli; do
	int_rc=0
	str_out="$(python3 "$GATE" --workflows "$REPO_ROOT/templates/$str_tier/.github/workflows" \
		--required-list "$REPO_ROOT/templates/$str_tier/bin/required-checks.txt" 2>&1)" || int_rc=$?
	check "list mode: shipped $str_tier list is all unconditional" "$int_rc" 0 "findings=0" "$str_out"
done

[ "$int_failures" -eq 0 ] || {
	echo "$int_failures case(s) failed"
	exit 1
}

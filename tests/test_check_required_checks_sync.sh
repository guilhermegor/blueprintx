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
	printf '["Lint gate", "App check"]' >"$str_tmp/req.json"
}

expect() {
	local str_out int_rc=0
	str_out="$(python3 -I "$GATE" --workflows "$str_tmp/wf" --policy "$str_tmp/policy.txt" \
		--required-file "$str_tmp/req.json" 2>&1)" || int_rc=$?
	if [ "$int_rc" -ne "$2" ] || ! grep -qF -- "$3" <<<"$str_out"; then
		echo "FAIL: $1 (exit $int_rc, wanted $2, needle '$3')"
		echo "$str_out"
		int_failures=$((int_failures + 1))
	else
		echo "ok: $1"
	fi
}

fixture
expect "in sync passes" 0 "findings=0"

printf '["Lint gate", "App check", "Ghost job"]' >"$str_tmp/req.json"
expect "required name no job emits fails" 1 "Ghost job"

printf '["Lint gate", "App check", "Filtered gate"]' >"$str_tmp/req.json"
expect "required name behind a branch filter fails" 1 "Filtered gate"

printf '["Lint gate", "App check", "Draft only"]' >"$str_tmp/req.json"
expect "required name behind a job if: fails" 1 "Draft only"

printf '["App check"]' >"$str_tmp/req.json"
expect "unconditional job neither required nor allowlisted fails" 1 "Lint gate"

printf 'optional|Lint gate|measured flaky\n' >>"$str_tmp/policy.txt"
expect "allowlisted optional job passes" 0 "findings=0"

printf 'optional|Gone job|stale\n' >>"$str_tmp/policy.txt"
expect "stale optional entry fails" 1 "Gone job"

fixture
printf 'optional|Lint gate|\n' >>"$str_tmp/policy.txt"
expect "policy line without a reason is rejected" 1 "need"

mkdir -p "$str_tmp/bin" && printf '#!/bin/sh\nexit 1\n' >"$str_tmp/bin/gh" && chmod +x "$str_tmp/bin/gh"
fixture
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" REQUIRED_CHECKS_SYNC_REQUIRED=1 python3 -I "$GATE" \
	--workflows "$str_tmp/wf" --policy "$str_tmp/policy.txt" 2>&1)" || int_rc=$?
if [ "$int_rc" -ne 1 ]; then echo "FAIL: unreadable API must fail closed in CI (exit $int_rc)"; int_failures=$((int_failures + 1)); else echo "ok: fails closed in CI"; fi
int_rc=0
str_out="$(PATH="$str_tmp/bin:$PATH" python3 -I "$GATE" --workflows "$str_tmp/wf" --policy "$str_tmp/policy.txt" 2>&1)" || int_rc=$?
if [ "$int_rc" -ne 0 ] || ! grep -q SKIPPED <<<"$str_out"; then echo "FAIL: local unreadable API must skip loudly"; int_failures=$((int_failures + 1)); else echo "ok: skips loudly locally"; fi

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }

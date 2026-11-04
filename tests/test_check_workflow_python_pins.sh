#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_workflow_python_pins.sh"

int_failures=0

expect_gate() {
	local str_got="pass" str_out
	str_out="$(PINS_REPO_ROOT="$3" bash "$GATE" 2>&1)" || str_got="fail"
	if [ "$str_got" != "$2" ]; then
		print_status "error" "$1 -> $str_got (expected $2): $str_out"
		int_failures=$((int_failures + 1))
		return
	fi
	print_status "success" "$1"
}

make_fixture() {
	local str_root
	str_root="$(mktemp -d)"
	mkdir -p "$str_root/templates/x/.github/workflows" "$str_root/.github/workflows"
	printf '        python-version: ["%s"]\n' "$1" >"$str_root/templates/x/.github/workflows/r.yaml"
	printf '          python-version: "%s"\n' "$2" >"$str_root/.github/workflows/c.yml"
	printf '%s' "$str_root"
}

expect_gate "real tree passes" pass "$REPO_ROOT"

str_fx="$(make_fixture 3.12 3.12)"
expect_gate "minor-only pins pass" pass "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture 3.12.8 3.12)"
expect_gate "template matrix pin 3.12.8 fails" fail "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture 3.12 3.11.4)"
expect_gate "root workflow pin 3.11.4 fails" fail "$str_fx"
rm -rf "$str_fx"

[ "$int_failures" -eq 0 ]

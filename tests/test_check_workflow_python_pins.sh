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
	str_root="$(mktemp -d -p "$str_tmp")"
	mkdir -p "$str_root/templates/x/.github/workflows" "$str_root/.github/workflows"
	printf '        python-version: ["%s"]\n' "$1" >"$str_root/templates/x/.github/workflows/r.yaml"
	printf '          python-version: "%s"\n' "$2" >"$str_root/.github/workflows/c.yml"
	printf '%s' "$str_root"
}

write_root_workflow() {
	printf '%b' "$2" >"$1/.github/workflows/c.yml"
}

str_tmp="$(mktemp -d)"
trap 'rm -rf "$str_tmp"' EXIT

expect_gate "real tree passes" pass "$REPO_ROOT"

str_fx="$(make_fixture 3.12 3.12)"
expect_gate "minor-only pins pass" pass "$str_fx"

str_fx="$(make_fixture 3.12.8 3.12)"
expect_gate "template matrix pin 3.12.8 fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.11.4)"
expect_gate "root workflow pin 3.11.4 fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version:\n      - "3.11"\n      - "3.12.8"\n'
expect_gate "multi-line matrix list with patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version:\n      - "3.11"\n      - "3.12"\n'
expect_gate "multi-line matrix list of minors passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    with: { python-version: 3.12.8 }\n'
expect_gate "inline flow map with patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: "3.12"  # was 3.12.8\n'
expect_gate "patch version only in trailing comment passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: pypy3.10-7.3.12\n'
expect_gate "pypy version string passes" pass "$str_fx"

str_fx="$(mktemp -d -p "$str_tmp")"
expect_gate "missing workflow dirs fail instead of passing vacuously" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: |\n      3.11\n      3.12.8\n'
expect_gate "block scalar with patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: >-\n      3.11\n      3.12\n    run: pip install foo==1.2.3\n'
expect_gate "block scalar of minors then a sibling key passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
rm -f "$str_fx"/.github/workflows/* "$str_fx"/templates/x/.github/workflows/*
expect_gate "zero workflow files fail instead of passing vacuously" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
mkdir -p "$str_fx/templates/x/node_modules/p/.github/workflows"
printf '    python-version: 3.9.1\n' >"$str_fx/templates/x/node_modules/p/.github/workflows/v.yml"
expect_gate "vendored node_modules workflows are not scanned" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
rm -rf "$str_fx/.github"
expect_gate "missing root workflows dir fails instead of a partial scan" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
rm -rf "$str_fx/templates"
expect_gate "missing templates dir fails instead of a partial scan" fail "$str_fx"

str_fx="$(make_fixture 3.12.8 3.12)"
str_out="$(PINS_REPO_ROOT="$str_fx" bash "$GATE" 2>&1 || true)"
case "$str_out" in
*"/templates/x/.github/workflows/r.yaml:1:"*) print_status "success" "hit names its file" ;;
*) print_status "error" "hit lacks file path: $str_out"; int_failures=$((int_failures + 1)) ;;
esac

[ "$int_failures" -eq 0 ]

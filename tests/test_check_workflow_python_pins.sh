#!/bin/bash

set -euo pipefail

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

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
write_root_workflow "$str_fx" '    with: { python-version: "3.12", other: 1.2.3 }\n'
expect_gate "flow map: later key with x.y.z is not a pin" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    run: echo "python-version: 3.12.8"\n'
expect_gate "python-version inside a run string is not a key" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
mkdir -p "$str_fx/templates/x/.github/workflows/locked"
chmod 000 "$str_fx/templates/x/.github/workflows/locked"
if [ "$(id -u)" -ne 0 ]; then
	expect_gate "unreadable subtree fails instead of a partial scan" fail "$str_fx"
fi
chmod 755 "$str_fx/templates/x/.github/workflows/locked"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: ["3.11", "3.12.8"]\n'
expect_gate "inline matrix with a later patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: ["3.11", "3.12"]\n'
expect_gate "inline matrix of minors passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
rm -rf "$str_fx/.github"
expect_gate "missing root workflows dir fails instead of a partial scan" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
rm -rf "$str_fx/templates"
expect_gate "missing templates dir fails instead of a partial scan" fail "$str_fx"

git_track() {
	git -C "$1" init -q
	git -C "$1" add -A
}

str_fx="$(make_fixture 3.12 3.12)"
git_track "$str_fx"
mkdir -p "$str_fx/templates/y/.github/workflows"
printf '    python-version: 3.12.8\n' >"$str_fx/templates/y/.github/workflows/new.yml"
expect_gate "untracked but not ignored workflow with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
git_track "$str_fx"
mkdir -p "$str_fx/templates/x/.github/workflows/locked"
chmod 000 "$str_fx/templates/x/.github/workflows/locked"
if [ "$(id -u)" -ne 0 ]; then
	expect_gate "unreadable subtree in a git work tree fails instead of a partial scan" fail "$str_fx"
fi
chmod 755 "$str_fx/templates/x/.github/workflows/locked"

str_fx="$(make_fixture 3.12 3.12)"
printf 'templates/y/\n' >"$str_fx/.gitignore"
mkdir -p "$str_fx/templates/y/.github/workflows"
printf '    python-version: 3.12.8\n' >"$str_fx/templates/y/.github/workflows/stale.yml"
git_track "$str_fx"
expect_gate "gitignored workflow is not scanned, matching CI" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'env:\n  PYTHON_VERSION: "3.12.8"\njobs:\n  a:\n    steps:\n      - with:\n          python-version: ${{ env.PYTHON_VERSION }}\n'
expect_gate "indirect env.PYTHON_VERSION holding a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'env:\n  PYTHON_VERSION: "3.12"\njobs:\n  a:\n    steps:\n      - with:\n          python-version: ${{ env.PYTHON_VERSION }}\n'
expect_gate "indirect env.PYTHON_VERSION holding a minor passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix:\n        py: ["3.11", "3.12.8"]\n    steps:\n      - with:\n          python-version: ${{ matrix.py }}\n'
expect_gate "indirect matrix.py holding a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix:\n        include:\n          - py: 3.12.8\n    steps:\n      - with:\n          python-version: ${{ matrix.py }}\n'
expect_gate "indirect matrix include entry with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix:\n        py: ["3.11", "3.12"]\n    steps:\n      - with:\n          python-version: ${{ matrix.py }}\n'
expect_gate "indirect matrix.py holding minors passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix:\n        version: ["3.12"]\n    steps:\n      - uses: astral-sh/setup-uv@v5\n        with:\n          version: "0.5.11"\n      - with:\n          python-version: ${{ matrix.version }}\n'
expect_gate "indirect name matching an unrelated with: key passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix:\n        version: ["1.2.3"]\n    steps:\n      - with:\n          python-version: ${{ inputs.version }}\n'
expect_gate "inputs name does not pool onto an unrelated matrix key" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'env: { PYTHON_VERSION: "3.12.8" }\njobs:\n  a:\n    steps:\n      - with:\n          python-version: ${{ env.PYTHON_VERSION }}\n'
expect_gate "flow-style env holding a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'jobs:\n  a:\n    strategy:\n      matrix: { py: ["3.12.8"] }\n    steps:\n      - with:\n          python-version: ${{ matrix.py }}\n'
expect_gate "flow-style matrix holding a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'on:\n  workflow_call:\n    inputs:\n      py:\n        type: string\n        default: "3.12.8"\njobs:\n  a:\n    steps:\n      - with:\n          python-version: ${{ inputs.py }}\n'
expect_gate "indirect inputs.py default holding a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" 'on:\n  workflow_call:\n    inputs:\n      py:\n        type: string\n        default: "3.12"\njobs:\n  a:\n    steps:\n      - with:\n          python-version: ${{ inputs.py }}\n'
expect_gate "indirect inputs.py default holding a minor passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: ${{ vars.PYTHON_VERSION }}\n'
expect_gate "vars.* pin lives outside the repo and fails as unverifiable" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version-file: .python-version\n'
expect_gate "python-version-file is unverifiable and fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: 3.10\n'
expect_gate "unquoted 3.10 (YAML float 3.1) fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: [3.9, 3.10]\n'
expect_gate "unquoted 3.10 in an inline list fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version:\n      - "3.9"\n      - 3.10\n'
expect_gate "unquoted 3.10 in a block list fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: "3.10"\n'
expect_gate "quoted 3.10 passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: |\n      3.10\n      3.12\n'
expect_gate "3.10 inside a block scalar is a string and passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    "python-version": "3.12.8"\n'
expect_gate "double-quoted key with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" "    'python-version': 3.12.8\n"
expect_gate "single-quoted key with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    run: echo "a, python-version: 3.12.8"\n'
expect_gate "python-version after a comma inside a run string passes" pass "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: "3.11\n      3.12.8"\n'
expect_gate "double-quoted continuation scalar with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: 3.11\n      3.12.8\n'
expect_gate "plain continuation scalar with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '    python-version: ["3.11",\n      "3.12.8"]\n'
expect_gate "multi-line flow list with a patch pin fails" fail "$str_fx"

str_fx="$(make_fixture 3.12 3.12)"
write_root_workflow "$str_fx" '      - python-version: "3.12"\n        run: pip install foo==1.2.3\n'
expect_gate "list-item key then a deeper sibling key passes" pass "$str_fx"

if grep -q 'mapfile' "$GATE"; then
	print_status "error" "gate uses mapfile, which needs bash 4.4 for -d (bash 3.2 has none)"
	int_failures=$((int_failures + 1))
else
	print_status "success" "gate avoids mapfile"
fi

if command -v busybox >/dev/null 2>&1; then
	str_fx="$(make_fixture 3.12.8 3.12)"
	str_got="pass"
	PINS_AWK="busybox awk" PINS_REPO_ROOT="$str_fx" bash "$GATE" >/dev/null 2>&1 || str_got="fail"
	if [ "$str_got" = "fail" ]; then
		print_status "success" "gate flags a patch pin under busybox awk"
	else
		print_status "error" "gate missed a patch pin under busybox awk"
		int_failures=$((int_failures + 1))
	fi
	str_fx="$(make_fixture 3.12 3.12)"
	str_got="pass"
	PINS_AWK="busybox awk" PINS_REPO_ROOT="$str_fx" bash "$GATE" >/dev/null 2>&1 || str_got="fail"
	if [ "$str_got" = "pass" ]; then
		print_status "success" "gate passes minors under busybox awk"
	else
		print_status "error" "gate rejected minors under busybox awk"
		int_failures=$((int_failures + 1))
	fi
fi

str_fx="$(make_fixture 3.12.8 3.12)"
str_out="$(PINS_REPO_ROOT="$str_fx" bash "$GATE" 2>&1 || true)"
case "$str_out" in
*"/templates/x/.github/workflows/r.yaml:1:"*) print_status "success" "hit names its file" ;;
*) print_status "error" "hit lacks file path: $str_out"; int_failures=$((int_failures + 1)) ;;
esac

[ "$int_failures" -eq 0 ]

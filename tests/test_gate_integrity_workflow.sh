#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
int_failures=0

pass() {
	printf 'ok   %s\n' "$1"
}

fail() {
	printf 'FAIL %s\n' "$1" >&2
	int_failures=$((int_failures + 1))
}

pull_request_types() {
	awk '
		/^on:/ { in_on = 1; next }
		in_on && /^[^[:space:]]/ { in_on = 0 }
		in_on && /^  pull_request:/ { in_pr = 1; next }
		in_on && in_pr && /^  [^[:space:]]/ { in_pr = 0 }
		in_on && in_pr && /^    types:/ { print; exit }
	' "$1"
}

check_edited_trigger() {
	local str_file="$1" str_types
	if [ ! -f "$REPO_ROOT/$str_file" ]; then
		fail "$str_file is missing"
		return
	fi
	str_types="$(pull_request_types "$REPO_ROOT/$str_file")"
	if [[ "$str_types" == *edited* ]]; then
		pass "$str_file: pull_request types include edited"
	else
		fail "$str_file: pull_request types do not include edited (got: '${str_types:-none}')"
	fi
}

check_absent() {
	local str_file="$1" str_pattern="$2" str_desc="$3"
	if grep -qF -- "$str_pattern" "$REPO_ROOT/$str_file"; then
		fail "$str_desc"
	else
		pass "$str_desc"
	fi
}

check_present() {
	local str_file="$1" str_pattern="$2" str_desc="$3"
	if grep -qF -- "$str_pattern" "$REPO_ROOT/$str_file"; then
		pass "$str_desc"
	else
		fail "$str_desc"
	fi
}

check_edited_trigger ".github/workflows/gate_integrity.yml"
check_edited_trigger "templates/python-common/.github/workflows/assertion-weakening.yml"

check_present ".github/workflows/gate_integrity.yml" "check_gate_integrity.py" \
	"gate_integrity.yml runs check_gate_integrity.py"
check_present ".github/workflows/gate_integrity.yml" \
	"name: Gate integrity — a PR must not weaken a check without saying why" \
	"gate_integrity.yml keeps the required-check display name"
check_present "templates/python-common/.github/workflows/assertion-weakening.yml" \
	"check_gate_integrity.py" "template assertion-weakening.yml runs check_gate_integrity.py"

check_absent ".github/workflows/scaffold_checks.yml" "check_gate_integrity.py" \
	"scaffold_checks.yml no longer runs check_gate_integrity.py"
check_absent "templates/python-common/.github/workflows/tests.yml" "check_gate_integrity.py" \
	"template tests.yml no longer runs check_gate_integrity.py"
check_absent ".github/workflows/scaffold_checks.yml" "edited" \
	"scaffold_checks.yml does not re-run the matrix on edited"

if [ "$int_failures" -gt 0 ]; then
	printf '%d check(s) failed\n' "$int_failures" >&2
	exit 1
fi
printf 'all checks passed\n'

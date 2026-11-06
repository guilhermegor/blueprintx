#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/bin/ci/check_workflow_names.sh"
DIR_SCRATCH="$(mktemp -d)"
trap 'rm -rf "$DIR_SCRATCH"' EXIT

int_failures=0
int_case=0

expect() {
	local str_expect="$1" str_tier="$2" str_name="$3" str_root int_rc=0
	int_case=$((int_case + 1))
	str_root="$DIR_SCRATCH/case$int_case"
	mkdir -p "$str_root/templates/$str_tier/.github/workflows"
	touch "$str_root/templates/$str_tier/.github/workflows/$str_name"
	bash "$GATE" --root "$str_root" >/dev/null 2>&1 || int_rc=$?
	if { [ "$str_expect" = "pass" ] && [ "$int_rc" -ne 0 ]; } || { [ "$str_expect" = "fail" ] && [ "$int_rc" -eq 0 ]; }; then
		echo "FAIL: $str_tier/$str_name expected $str_expect, rc=$int_rc" >&2
		int_failures=$((int_failures + 1))
	fi
}

expect pass python-common review-threads.yml
expect pass lib-minimal release-pypi.yaml
expect pass lib-minimal release-test-pypi.yaml
expect fail python-common release-pypi.yaml
expect fail python-common review_threads.yml
expect fail python-common review-threads.yaml
expect fail python-common Review-Threads.yml
expect fail lib-minimal release_pypi.yaml

int_rc=0
mkdir -p "$DIR_SCRATCH/empty"
bash "$GATE" --root "$DIR_SCRATCH/empty" >/dev/null 2>&1 || int_rc=$?
if [ "$int_rc" -eq 0 ]; then
	echo "FAIL: an empty tree must not pass" >&2
	int_failures=$((int_failures + 1))
fi

bash "$GATE" >/dev/null || { echo "FAIL: the real templates tree does not conform" >&2; int_failures=$((int_failures + 1)); }

[ "$int_failures" -eq 0 ] && echo "PASS: check_workflow_names" || exit 1

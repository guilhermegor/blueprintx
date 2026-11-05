#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/bin/ci/check_workflow_names.sh"

int_failures=0

make_root() {
	local str_root
	str_root="$(mktemp -d)"
	mkdir -p "$str_root/templates/x/.github/workflows"
	touch "$str_root/templates/x/.github/workflows/$1"
	printf '%s' "$str_root"
}

expect() {
	local str_expect="$1" str_name="$2" str_root int_rc=0
	str_root="$(make_root "$str_name")"
	bash "$GATE" --root "$str_root" >/dev/null 2>&1 || int_rc=$?
	if [ "$str_expect" = "pass" ] && [ "$int_rc" -ne 0 ] || [ "$str_expect" = "fail" ] && [ "$int_rc" -eq 0 ]; then
		echo "FAIL: $str_name expected $str_expect, rc=$int_rc" >&2
		int_failures=$((int_failures + 1))
	fi
}

expect pass review-threads.yml
expect pass release-pypi.yaml
expect pass release-test-pypi.yaml
expect fail review_threads.yml
expect fail review-threads.yaml
expect fail Review-Threads.yml
expect fail release_pypi.yaml

int_rc=0
bash "$GATE" --root "$(mktemp -d)" >/dev/null 2>&1 || int_rc=$?
if [ "$int_rc" -eq 0 ]; then
	echo "FAIL: an empty tree must not pass" >&2
	int_failures=$((int_failures + 1))
fi

bash "$GATE" >/dev/null || { echo "FAIL: the real templates tree does not conform" >&2; int_failures=$((int_failures + 1)); }

[ "$int_failures" -eq 0 ] && echo "PASS: check_workflow_names" || exit 1

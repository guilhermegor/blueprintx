#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
int_failures=0

for str_wf in \
	templates/lib-minimal/.github/workflows/release-pypi.yaml \
	templates/ts-lib/.github/workflows/release-npm.yml; do
	if ! grep -qF 'target_commitish: ${{ github.sha }}' "$REPO_ROOT/$str_wf"; then
		echo "FAIL: $str_wf does not pin the release tag to github.sha" >&2
		int_failures=$((int_failures + 1))
	fi
done

exit "$int_failures"

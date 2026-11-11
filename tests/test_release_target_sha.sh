#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
str_pin_re='^[[:space:]]+target_commitish:[[:space:]]*\$\{\{[[:space:]]*github\.sha[[:space:]]*\}\}'

pins_release() {
	grep -Eq "$str_pin_re" "$1"
}

int_failures=0
int_checked=0

while IFS= read -r str_wf; do
	int_checked=$((int_checked + 1))
	if ! pins_release "$str_wf"; then
		echo "FAIL: $str_wf does not pin the release tag to github.sha" >&2
		int_failures=$((int_failures + 1))
	fi
done < <(grep -rlE 'uses:[[:space:]]*softprops/action-gh-release' \
	--include='*.yml' --include='*.yaml' "$REPO_ROOT"/templates)

if [ "$int_checked" -eq 0 ]; then
	echo "FAIL: no release workflow found to check" >&2
	exit 1
fi

str_tmp="$(mktemp)"
trap 'rm -f "$str_tmp"' EXIT
# shellcheck disable=SC2016
printf '      with:\n        # target_commitish: ${{ github.sha }}\n' >"$str_tmp"
if pins_release "$str_tmp"; then
	echo "FAIL: witness, a commented-out pin was accepted" >&2
	int_failures=$((int_failures + 1))
fi

echo "checked $int_checked release workflow(s), $int_failures failure(s)"
exit $((int_failures > 0))

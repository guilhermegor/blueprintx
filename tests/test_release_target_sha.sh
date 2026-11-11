#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
str_use_re='^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*["'"'"']?softprops/action-gh-release'
str_pin_re='^[[:space:]]+target_commitish:[[:space:]]*["'"'"']?\$\{\{[[:space:]]*github\.sha[[:space:]]*\}\}'

count_matches() {
	grep -Ec "$1" "$2" || true
}

pins_every_release() {
	local int_uses int_pins
	int_uses="$(count_matches "$str_use_re" "$1")"
	int_pins="$(count_matches "$str_pin_re" "$1")"
	[ "$int_uses" -gt 0 ] && [ "$int_uses" -eq "$int_pins" ]
}

expect_witness() {
	local str_name="$1" str_body="$2" str_want="$3" str_tmp
	str_tmp="$(mktemp)"
	printf '%s\n' "$str_body" >"$str_tmp"
	if pins_every_release "$str_tmp"; then
		[ "$str_want" = accept ] || { echo "FAIL: witness '$str_name' was accepted" >&2; int_failures=$((int_failures + 1)); }
	else
		[ "$str_want" = reject ] || { echo "FAIL: witness '$str_name' was rejected" >&2; int_failures=$((int_failures + 1)); }
	fi
	rm -f "$str_tmp"
}

int_failures=0
int_checked=0

while IFS= read -r str_wf; do
	int_checked=$((int_checked + 1))
	if ! pins_every_release "$str_wf"; then
		echo "FAIL: $str_wf does not pin every release step to github.sha" >&2
		int_failures=$((int_failures + 1))
	fi
done < <(grep -rlE "$str_use_re" --include='*.yml' --include='*.yaml' "$REPO_ROOT"/templates)

if [ "$int_checked" -eq 0 ]; then
	echo "FAIL: no release workflow found to check" >&2
	exit 1
fi

str_use='      - uses: softprops/action-gh-release@v2'
str_pin="        target_commitish: \${{ github.sha }}"
expect_witness "commented-out pin" "$str_use
${str_pin/ target/ \# target}" reject
expect_witness "two steps, one pin" "$str_use
$str_pin
$str_use" reject
expect_witness "quoted uses is discovered" "      - uses: \"softprops/action-gh-release@v2\"" reject
expect_witness "pinned step" "$str_use
$str_pin" accept
expect_witness "quoted pin" "$str_use
        target_commitish: \"\${{ github.sha }}\"" accept

echo "checked $int_checked release workflow(s), $int_failures failure(s)"
exit $((int_failures > 0))

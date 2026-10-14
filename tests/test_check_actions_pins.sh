#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_actions.sh"

int_failures=0

run_pin_check() {
	local str_file="$1"
	(
		# shellcheck disable=SC1090
		source <(sed '/^main "\$@"$/d' "$GATE")
		check_action_pins "$str_file"
	) 2>&1
}

write_workflow() {
	local str_uses="$1" str_file
	str_file="$(mktemp -d)/witness.yml"
	cat > "$str_file" <<EOF
name: witness
on: push
jobs:
  witness:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: $str_uses
EOF
	printf '%s' "$str_file"
}

expect_gate() {
	local str_desc="$1" str_want="$2" str_needle="$3" str_file str_got="pass" str_out
	str_file="$(write_workflow "$4")"
	str_out="$(run_pin_check "$str_file")" || str_got="fail"
	rm -rf "$(dirname "$str_file")"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
		int_failures=$((int_failures + 1))
		return
	fi
	if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
		print_status "error" "$str_desc -> $str_want, but never said '$str_needle': $str_out"
		int_failures=$((int_failures + 1))
	fi
}

main() {
	local str_sha="11d5960a326750d5838078e36cf38b85af677262"
	expect_gate "tag reference" "fail" ":8: not pinned to a commit SHA: foo/bar@v1" "foo/bar@v1"
	expect_gate "branch reference" "fail" "foo/bar@release/v1" "foo/bar@release/v1"
	expect_gate "SHA without version comment" "fail" "foo/bar@$str_sha" "foo/bar@$str_sha"
	expect_gate "short SHA" "fail" "foo/bar@11d5960" "foo/bar@11d5960 # v4.4.0"
	expect_gate "full SHA with version comment" "pass" "1 SHA-pinned" "foo/bar@$str_sha # v4.4.0"
	expect_gate "local reusable workflow" "pass" "0 SHA-pinned" "./.github/workflows/x.yml"

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures check_action_pins regression assertion(s) failed"
		exit 1
	fi
	print_status "success" \
		"check_action_pins: tag, branch, bare SHA and short SHA fail naming the reference; full SHA + version comment and local reusable workflow pass"
}

main "$@"

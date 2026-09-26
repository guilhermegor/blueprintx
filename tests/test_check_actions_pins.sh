#!/bin/bash
# Should-fail regression tests for check_action_pins in bin/ci/check_actions.sh (blueprintx#369).
#
# The gate's only interface is a workflow file, so each case writes a real one into a
# throwaway directory and runs the function over it. A tag reference must fail NAMING the
# file, line and reference (a crash also exits non-zero); a full-SHA reference with its
# version comment must pass; a SHA without the comment must fail, because that is the
# shape Dependabot cannot bump.
#
# Usage: bash tests/test_check_actions_pins.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_actions.sh"

int_failures=0

# Loads the gate's functions without running main: everything after the `main "$@"` line is
# dropped, and `set -e` inside the sourced text is neutralised by running in a subshell.
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
	str_file="$(mktemp --suffix=.yml)"
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
	# $1 = description, $2 = expected pass|fail, $3 = needle that must appear, $4 = uses: value.
	local str_desc="$1" str_want="$2" str_needle="$3" str_file str_got="pass" str_out
	str_file="$(write_workflow "$4")"
	str_out="$(run_pin_check "$str_file")" || str_got="fail"
	rm -f "$str_file"
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

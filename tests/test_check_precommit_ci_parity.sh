#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

make_sandbox() {
	local str_root
	str_root="$(mktemp -d)"
	mkdir -p "$str_root/bin/lib" "$str_root/bin/ci" "$str_root/.github/workflows"
	cp "$REPO_ROOT/bin/check_precommit_ci_parity.sh" "$str_root/bin/check_precommit_ci_parity.sh"
	cp "$REPO_ROOT/bin/lib/common.sh" "$str_root/bin/lib/common.sh"
	printf '%s' "$str_root"
}

write_precommit() {
	local str_root="$1"
	shift
	{
		echo "repos:"
		echo "  - repo: local"
		echo "    hooks:"
		local str_line
		for str_line in "$@"; do
			printf '      %s\n' "$str_line"
		done
	} >"$str_root/.pre-commit-config.yaml"
}

write_workflow() {
	local str_root="$1" str_name="$2"
	shift 2
	{
		echo "jobs:"
		echo "  a-job:"
		echo "    steps:"
		local str_line
		for str_line in "$@"; do
			printf '      - %s\n' "$str_line"
		done
	} >"$str_root/.github/workflows/$str_name"
}

expect_gate() {
	local str_desc="$1" str_root="$2" str_want="$3" str_needle="${4:-}" str_got="pass" str_out
	str_out="$(bash "$str_root/bin/check_precommit_ci_parity.sh" 2>&1)" || str_got="fail"
	rm -rf "$str_root"
	if [ "$str_got" != "$str_want" ]; then
		print_status "error" "$str_desc -> $str_got (expected $str_want)"
		int_failures=$((int_failures + 1))
		return
	fi
	if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF "$str_needle"; then
		print_status "error" "$str_desc -> $str_got, but never said '$str_needle'"
		int_failures=$((int_failures + 1))
	fi
}

test_matched_on_both_sides_passes() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root" "entry: bash bin/ci/check_foo.sh"
	write_workflow "$str_root" "checks.yml" "run: bash bin/ci/check_foo.sh"
	expect_gate "a script wired into both sides" "$str_root" "pass"
}

test_precommit_only_fails() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root" "entry: bash bin/ci/check_foo.sh"
	expect_gate "a pre-commit-only script with no exemption" "$str_root" "fail" \
		"check_foo.sh runs in pre-commit but no CI workflow references it"
}

test_ci_only_fails() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root"
	write_workflow "$str_root" "checks.yml" "run: bash bin/ci/check_foo.sh"
	expect_gate "a CI-only script with no exemption" "$str_root" "fail" \
		"check_foo.sh runs in CI but no pre-commit hook references it"
}

test_exempted_ci_only_passes() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root"
	write_workflow "$str_root" "checks.yml" "run: bash bin/ci/check_foo.sh"
	echo "check_foo.sh|ci_only|too heavy for a pre-commit hook, see #1" \
		>"$str_root/bin/precommit_ci_parity_exemptions.txt"
	expect_gate "a CI-only script with a reasoned exemption" "$str_root" "pass"
}

test_exemption_without_reason_rejected() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root"
	write_workflow "$str_root" "checks.yml" "run: bash bin/ci/check_foo.sh"
	echo "check_foo.sh|ci_only|" >"$str_root/bin/precommit_ci_parity_exemptions.txt"
	expect_gate "an exemption with no reason" "$str_root" "fail" \
		"has no reason — rejected"
}

test_zero_discovery_fails() {
	local str_root
	str_root="$(make_sandbox)"
	write_precommit "$str_root"
	expect_gate "zero candidate scripts discovered" "$str_root" "fail" \
		"discovered ZERO candidate scripts"
}

test_secret_scan_style_cross_workflow_match_passes() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_secrets_like.sh"
	write_precommit "$str_root" "entry: bash bin/ci/check_secrets_like.sh"
	write_workflow "$str_root" "unrelated.yml" "run: echo noop"
	write_workflow "$str_root" "secret_scan.yml" "run: bash bin/ci/check_secrets_like.sh"
	expect_gate "a script found only in the SECOND workflow file" "$str_root" "pass"
}

test_comment_mention_is_not_invocation() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root" "entry: bash bin/ci/check_foo.sh"
	write_workflow "$str_root" "checks.yml" "run: echo noop"
	printf '        # see bin/ci/check_foo.sh for the rationale\n' \
		>>"$str_root/.github/workflows/checks.yml"
	expect_gate "a script named only in a workflow COMMENT" "$str_root" "fail" \
		"check_foo.sh runs in pre-commit but no CI workflow references it"
}

test_malformed_exemption_rejected_even_when_unused() {
	local str_root
	str_root="$(make_sandbox)"
	: >"$str_root/bin/ci/check_foo.sh"
	write_precommit "$str_root" "entry: bash bin/ci/check_foo.sh"
	write_workflow "$str_root" "checks.yml" "run: bash bin/ci/check_foo.sh"
	echo "stale.sh|unexpected|a side that is neither precommit_only nor ci_only" \
		>"$str_root/bin/precommit_ci_parity_exemptions.txt"
	expect_gate "a malformed exemption entry no candidate needs" "$str_root" "fail" \
		"invalid side 'unexpected'"
}

main() {
	test_matched_on_both_sides_passes
	test_precommit_only_fails
	test_ci_only_fails
	test_exempted_ci_only_passes
	test_exemption_without_reason_rejected
	test_zero_discovery_fails
	test_secret_scan_style_cross_workflow_match_passes
	test_comment_mention_is_not_invocation
	test_malformed_exemption_rejected_even_when_unused

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures check_precommit_ci_parity.sh regression assertion(s) failed"
		exit 1
	fi
	print_status "success" \
		"check_precommit_ci_parity.sh rejects one-sided scripts, requires a reason to exempt one, refuses zero discovery, and scans every workflow file"
}

main "$@"

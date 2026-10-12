#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/templates/python-common/bin/check_secrets.sh"

unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX

int_failures=0
LIST_TMP=()
trap 'rm -rf "${LIST_TMP[@]}"' EXIT

fake_secret() {
	printf '%s%s' "ghp_" "R8kT2mXq9LwZ4vNc7YbH1dJf5GsA3pUe6QoE"
}

make_repo() {
	local str_repo
	str_repo="$(mktemp -d)"
	LIST_TMP+=("$str_repo")
	git -C "$str_repo" init --quiet --initial-branch=main
	git -C "$str_repo" config user.email "test@example.com"
	git -C "$str_repo" config user.name "Test"
	echo "seed" >"$str_repo/seed.txt"
	git -C "$str_repo" add seed.txt
	git -C "$str_repo" commit --quiet -m "seed"
	printf '%s' "$str_repo"
}

expect_gate() {
	local str_label="$1" str_expect="$2" str_repo="$3" int_rc=0
	shift 3
	bash "$GATE" --root "$str_repo" "$@" >/dev/null 2>&1 || int_rc=$?
	if { [ "$str_expect" = "pass" ] && [ "$int_rc" -eq 0 ]; } ||
		{ [ "$str_expect" = "fail" ] && [ "$int_rc" -eq 1 ]; }; then
		print_status "success" "$str_label: $str_expect (exit $int_rc)"
		return 0
	fi
	print_status "error" "$str_label: expected $str_expect, got exit $int_rc"
	int_failures=$((int_failures + 1))
}

path_without_gitleaks() {
	local str_dir str_out="" list_dirs
	IFS=: read -ra list_dirs <<<"$PATH"
	for str_dir in "${list_dirs[@]}"; do
		[ -x "$str_dir/gitleaks" ] || str_out="${str_out:+$str_out:}$str_dir"
	done
	printf '%s' "$str_out"
}

test_absent_gitleaks() {
	local int_rc=0 str_path
	str_path="$(path_without_gitleaks)"
	if PATH="$str_path" command -v gitleaks >/dev/null 2>&1; then
		print_status "warning" "SKIPPED absent-gitleaks cases: cannot hide gitleaks from PATH"
		return 0
	fi
	PATH="$str_path" bash "$GATE" --staged >/dev/null 2>&1 || int_rc=$?
	if [ "$int_rc" -ne 0 ]; then
		print_status "error" "absent gitleaks must skip gracefully, got exit $int_rc"
		int_failures=$((int_failures + 1))
	fi
	int_rc=0
	GITLEAKS_REQUIRED=1 PATH="$str_path" bash "$GATE" --staged >/dev/null 2>&1 || int_rc=$?
	if [ "$int_rc" -ne 1 ]; then
		print_status "error" "GITLEAKS_REQUIRED=1 with gitleaks absent must exit 1, got $int_rc"
		int_failures=$((int_failures + 1))
	fi
}

test_staged_secret_is_caught() {
	local str_repo
	str_repo="$(make_repo)"
	fake_secret >"$str_repo/config.txt"
	git -C "$str_repo" add config.txt
	expect_gate "staged secret, staged mode" "fail" "$str_repo" --staged
}

test_clean_staged_change_passes() {
	local str_repo
	str_repo="$(make_repo)"
	echo "harmless" >"$str_repo/notes.txt"
	git -C "$str_repo" add notes.txt
	expect_gate "clean staged change, staged mode" "pass" "$str_repo" --staged
}

test_old_history_secret_full_mode_only() {
	local str_repo
	str_repo="$(make_repo)"
	fake_secret >"$str_repo/leak.txt"
	git -C "$str_repo" add leak.txt
	git -C "$str_repo" commit --quiet -m "oops"
	git -C "$str_repo" rm --quiet leak.txt
	git -C "$str_repo" commit --quiet -m "remove"
	echo "harmless" >"$str_repo/notes.txt"
	git -C "$str_repo" add notes.txt
	expect_gate "old-history secret, full mode" "fail" "$str_repo"
	expect_gate "old-history secret, staged mode" "pass" "$str_repo" --staged
}

main() {
	test_absent_gitleaks
	if ! command -v gitleaks >/dev/null 2>&1; then
		print_status "warning" "SKIPPED staged/full scan cases: gitleaks is not installed"
	else
		test_staged_secret_is_caught
		test_clean_staged_change_passes
		test_old_history_secret_full_mode_only
	fi

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" "$int_failures check_secrets.sh regression assertion(s) failed"
		exit 1
	fi
	print_status "success" "check_secrets.sh: staged and full modes behave as specified"
}

main "$@"

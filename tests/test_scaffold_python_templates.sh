#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

make_root() {
	local path_root="$1"
	mkdir -p "$path_root/bin/lib"
	cp "$REPO_ROOT/bin/lib/scaffold_provenance.sh" "$path_root/bin/lib/"
	echo 'BLUEPRINTX_VERSION="9.9.9"' >"$path_root/bin/blueprintx.sh"
}

stamp() {
	local path_root="$1" path_project="$2" str_tier="$3"
	mkdir -p "$path_project"
	BLUEPRINTX_ROOT="$path_root" bash -c 'source "$BLUEPRINTX_ROOT/bin/lib/scaffold_provenance.sh"; scaffold_stamp_provenance "$1" "$2"' _ "$str_tier" "$path_project"
}

seed_repo() {
	git -C "$1" init -q -b main
	git -C "$1" add -A
	git -C "$1" -c user.email=t@example.com -c user.name=T commit -q -m "chore: seed"
	git -C "$1" tag "$2"
}

test_packaged_install_nested_in_a_foreign_repo_uses_the_literal() {
	local path_outer="$WORK_DIR/outer"
	make_root "$path_outer/pkg"
	seed_repo "$path_outer" v1.2.3
	stamp "$path_outer/pkg" "$WORK_DIR/p1" mvc-service-native-db
	if grep -qx 'blueprintx_version: 9.9.9' "$WORK_DIR/p1/.blueprintx-provenance.yaml" \
		&& grep -qx 'blueprintx_commit: unknown' "$WORK_DIR/p1/.blueprintx-provenance.yaml"; then
		pass "a root without its own .git never stamps the enclosing repo"
	else
		fail "nested install" "$(tr '\n' '|' <"$WORK_DIR/p1/.blueprintx-provenance.yaml")"
	fi
}

test_a_checkout_stamps_its_own_tag_and_commit() {
	local path_root="$WORK_DIR/checkout" str_head
	make_root "$path_root"
	seed_repo "$path_root" v0.1.0
	str_head="$(git -C "$path_root" rev-parse HEAD)"
	stamp "$path_root" "$WORK_DIR/p2" lib-minimal
	if grep -qx 'blueprintx_version: 0.1.0' "$WORK_DIR/p2/.blueprintx-provenance.yaml" \
		&& grep -qx "blueprintx_commit: $str_head" "$WORK_DIR/p2/.blueprintx-provenance.yaml" \
		&& grep -qx 'tier: lib-minimal' "$WORK_DIR/p2/.blueprintx-provenance.yaml"; then
		pass "a git checkout stamps its own tag and HEAD"
	else
		fail "checkout" "$(tr '\n' '|' <"$WORK_DIR/p2/.blueprintx-provenance.yaml")"
	fi
}

test_lib_minimal_has_no_stamp_function_of_its_own() {
	if grep -q 'blueprintx-provenance\|lib_minimal_stamp_provenance' "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh"; then
		fail "collapse" "python_lib_minimal.sh grew its own provenance logic again"
	else
		pass "python_lib_minimal.sh calls the shared stamp, no copy"
	fi
}

test_packaged_install_nested_in_a_foreign_repo_uses_the_literal
test_a_checkout_stamps_its_own_tag_and_commit
test_lib_minimal_has_no_stamp_function_of_its_own

exit "$int_failures"

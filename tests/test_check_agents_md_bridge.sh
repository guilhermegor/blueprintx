#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
GATE="$REPO_ROOT/bin/ci/check_agents_md_bridge.sh"

int_failures=0

make_fixture() {
	local str_root
	str_root="$(mktemp -d)"
	mkdir -p "$str_root/templates" "$str_root/bin"
	cp -r "$REPO_ROOT/templates/lib-minimal" "$str_root/templates/lib-minimal"
	cp -r "$REPO_ROOT/bin/scaffold" "$REPO_ROOT/bin/lib" "$str_root/bin/"
	mkdir -p "$str_root/templates/common"
	cp "$REPO_ROOT/templates/common/PRINCIPLES.md" "$str_root/templates/common/"
	printf '%s' "$str_root"
}

expect_gate() {
	local str_got="pass" str_out
	str_out="$(BRIDGE_REPO_ROOT="$4" bash "$GATE" 2>&1)" || str_got="fail"
	if [ "$str_got" != "$2" ]; then
		print_status "error" "$1 -> $str_got (expected $2): $str_out"
		int_failures=$((int_failures + 1))
		return
	fi
	if [ -n "$3" ] && ! grep -qF -- "$3" <<<"$str_out"; then
		print_status "error" "$1 -> never said '$3': $str_out"
		int_failures=$((int_failures + 1))
		return
	fi
	print_status "success" "$1"
}

expect_gate "real tree passes" pass "bridges OK" "$REPO_ROOT"

str_fx="$(make_fixture)"
printf '@NOPE.md\n' >>"$str_fx/templates/lib-minimal/CLAUDE.md"
expect_gate "import of a missing file fails" fail "@NOPE.md" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
printf '\nSome extra guidance paragraph.\n' >>"$str_fx/templates/lib-minimal/CLAUDE.md"
expect_gate "bridge with an extra paragraph fails" fail "outside the allowlist" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
sed -i 's#/PRINCIPLES.md"#/OTHER.md"#g' "$str_fx/bin/scaffold/python_lib_minimal.sh" "$str_fx"/bin/lib/*.sh
expect_gate "import the scaffold never copies fails" fail "never copies" "$str_fx"
rm -rf "$str_fx"

[ "$int_failures" -eq 0 ]

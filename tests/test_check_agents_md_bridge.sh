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
	mkdir -p "$str_root/templates/common/bin"
	cp "$REPO_ROOT/templates/common/bin/check_agents_md_pairs.sh" "$str_root/templates/common/bin/"
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
sed_inplace 's#/PRINCIPLES.md"#/OTHER.md"#g' "$str_fx/bin/scaffold/python_lib_minimal.sh"
expect_gate "import copied only by an unsourced helper fails" fail "never copies" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
printf '<!-- Edit AGENTS.md, not this file. Claude-Code-only lines go below this one. -->\n' >"$str_fx/templates/lib-minimal/CLAUDE.md"
expect_gate "bridge without @AGENTS.md fails" fail "does not import @AGENTS.md" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
rm "$str_fx/templates/lib-minimal/CLAUDE.md"
expect_gate "zero bridges fails" fail "checked nothing" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
sed_inplace 's#"\$project_path/PRINCIPLES.md"#"$project_path/.claude/PRINCIPLES.md"#' "$str_fx/bin/scaffold/python_lib_minimal.sh"
expect_gate "import copied to a different destination fails" fail "never copies" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
mkdir -p "$str_fx/templates/orphan"
cp "$str_fx/templates/lib-minimal/skeleton.meta" "$str_fx/templates/orphan/skeleton.meta"
expect_gate "skeleton without a bridge fails" fail "missing CLAUDE.md bridge" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
rm "$str_fx/templates/lib-minimal/docs/AGENTS.md"
expect_gate "leaf without a sibling AGENTS.md fails" fail "has no sibling AGENTS.md" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
printf '@AGENTS.md\n\nSome guidance.\n\nEdit AGENTS.md, not this file. Claude-Code-only lines go below this one.\n' \
	>"$str_fx/templates/lib-minimal/docs/CLAUDE.md"
expect_gate "leaf with content above the marker fails" fail "non-import line above the marker" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
printf '@AGENTS.md\n@NOPE.md\n\nEdit AGENTS.md, not this file. Claude-Code-only lines go below this one.\n' \
	>"$str_fx/templates/lib-minimal/docs/CLAUDE.md"
expect_gate "leaf with a broken import fails" fail "@NOPE.md but no such file exists" "$str_fx"
rm -rf "$str_fx"

str_fx="$(make_fixture)"
printf '@AGENTS.md\n' >"$str_fx/templates/lib-minimal/docs/CLAUDE.md"
expect_gate "leaf without the marker fails" fail "lacks the marker line" "$str_fx"
rm -rf "$str_fx"

[ "$int_failures" -eq 0 ]

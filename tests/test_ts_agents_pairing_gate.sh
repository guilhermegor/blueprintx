#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/templates/common/bin/check_agents_md_pairs.sh"
int_failures=0

expect() {
	local str_desc="$1" str_want="$2" str_got="$3"
	if [ "$str_got" = "$str_want" ]; then
		printf 'ok   %s\n' "$str_desc"
	else
		printf 'FAIL %s (got %s, want %s)\n' "$str_desc" "$str_got" "$str_want"
		int_failures=$((int_failures + 1))
	fi
}

has() {
	local str_got="no"
	grep -qF -- "$2" "$3" && str_got="yes"
	expect "$1" yes "$str_got"
}

for str_pkg in templates/ts-common/package.json templates/ts-lib/package.json; do
	has "$str_pkg wires lint:agents" '"lint:agents": "bash bin/check_agents_md_pairs.sh --root ."' "$REPO_ROOT/$str_pkg"
done
has "husky pre-commit runs the gate" 'bash bin/check_agents_md_pairs.sh --root .' "$REPO_ROOT/templates/ts-common/.husky/pre-commit"
has "lint.yml runs the gate" 'run: bash bin/check_agents_md_pairs.sh --root .' "$REPO_ROOT/templates/ts-common/.github/workflows/lint.yml"

str_proj="$(mktemp -d)"
trap 'rm -rf "$str_proj"' EXIT
mkdir -p "$str_proj/bin" "$str_proj/src/feat"
cp "$GATE" "$str_proj/bin/check_agents_md_pairs.sh"
printf 'rules\n' >"$str_proj/src/feat/AGENTS.md"
printf '@AGENTS.md\n\nEdit AGENTS.md, not this file. Claude-Code-only lines go below this one.\n' >"$str_proj/src/feat/CLAUDE.md"
bash "$str_proj/bin/check_agents_md_pairs.sh" --root "$str_proj" >/dev/null 2>&1
expect "paired leaf passes" 0 "$?"
rm "$str_proj/src/feat/AGENTS.md"
bash "$str_proj/bin/check_agents_md_pairs.sh" --root "$str_proj" >/dev/null 2>&1
expect "leaf CLAUDE.md without AGENTS.md fails" 1 "$?"

[ "$int_failures" -eq 0 ]

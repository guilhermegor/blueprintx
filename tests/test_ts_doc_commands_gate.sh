#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/templates/ts-common/bin/check_doc_commands.sh"
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

has_text() {
	local str_got="no"
	case "$3" in *"$2"*) str_got="yes" ;; esac
	expect "$1" yes "$str_got"
}

for str_pkg in templates/ts-common/package.json templates/ts-lib/package.json; do
	has "$str_pkg wires lint:docs" '"lint:docs": "bash bin/check_doc_commands.sh ."' "$REPO_ROOT/$str_pkg"
done
has "husky pre-commit runs the gate" 'bash bin/check_doc_commands.sh .' "$REPO_ROOT/templates/ts-common/.husky/pre-commit"
has "lint.yml runs the gate" 'run: bash bin/check_doc_commands.sh .' "$REPO_ROOT/templates/ts-common/.github/workflows/lint.yml"
for str_scaffold in ts_lib ts_react_app; do
	has "$str_scaffold copies the gate" 'bin/check_doc_commands.sh' "$REPO_ROOT/bin/scaffold/$str_scaffold.sh"
done

str_proj="$(mktemp -d)"
str_spa="$(mktemp -d)"
str_bad="$(mktemp -d)"
str_nonode="$(mktemp -d)"
trap 'rm -rf "$str_proj" "$str_spa" "$str_bad" "$str_nonode"' EXIT
has "scaffold_ts_test runs lint:docs in the generated project" 'npm run lint:docs' "$REPO_ROOT/bin/ci/scaffold_ts_test.sh"
mkdir -p "$str_proj/docs"
printf '{"scripts":{"build":"x","lint:css":"y"}}\n' >"$str_proj/package.json"
printf 'Run `npm run build` and `npm run lint:css`.\n' >"$str_proj/README.md"
printf 'See `npm run build`.\n' >"$str_proj/docs/usage.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "documented scripts that exist pass" 0 "$?"

printf 'Run `npm run dev`.\n' >"$str_proj/CLAUDE.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "CLAUDE.md citing a missing script fails" 1 "$?"
rm "$str_proj/CLAUDE.md"

printf 'Run `npm run dev`.\n' >"$str_proj/AGENTS.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "AGENTS.md citing a missing script fails" 1 "$?"
rm "$str_proj/AGENTS.md"

printf 'Run `npm run _ghost`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a missing underscore-prefixed script fails" 1 "$?"
printf 'Run _npm run build_ in italics.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "an italic closing underscore is not part of the name" 0 "$?"

printf 'Run `npm run --silent build`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "CONTRIBUTING.md with an npm flag after run passes" 0 "$?"
printf 'Run `npm run --silent ghost`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "CONTRIBUTING.md citing a missing script after a flag fails" 1 "$?"
for str_form in '-w app' '--workspace app' '--workspace=app' '--prefix app'; do
	printf 'Run `npm run %s ghost`.\n' "$str_form" >"$str_proj/CONTRIBUTING.md"
	bash "$GATE" "$str_proj" >/dev/null 2>&1
	expect "'$str_form' targets another manifest, so the root is not checked" 0 "$?"
done
printf 'Run `npm run --loglevel warn ghost`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a missing script after --loglevel warn fails" 1 "$?"
printf 'Run `npm run --loglevel warn build`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "an existing script after --loglevel warn passes" 0 "$?"
printf 'Run `pnpm run ghost`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "pnpm run is not an npm run command" 0 "$?"
printf 'Run `npm run build.prod` then `npm run build:`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a dotted missing script fails, trailing colon is prose" 1 "$?"
printf 'Run `npm run build:`.\n' >"$str_proj/CONTRIBUTING.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "trailing punctuation is not part of the script name" 0 "$?"
rm "$str_proj/CONTRIBUTING.md"

mkdir -p "$str_proj/docs/node_modules/pkg"
printf 'Run `npm run vendored-ghost`.\n' >"$str_proj/docs/node_modules/pkg/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "vendored docs under node_modules are not scanned" 0 "$?"
rm -rf "$str_proj/docs/node_modules"

printf 'Try `npm run serve`.\n' >"$str_proj/docs/usage.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "docs/ citing a missing script fails" 1 "$?"

printf 'Try `npm run serve` # doc-commands:optional\n' >"$str_proj/docs/usage.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a doc-commands:optional line is exempt" 0 "$?"

cp "$REPO_ROOT/templates/ts-common/package.json" "$str_spa/package.json"
cp "$REPO_ROOT/templates/react-spa-webpack/README.md" "$str_spa/README.md"
bash "$GATE" "$str_spa" >/dev/null 2>&1
expect "react-spa README matches ts-common scripts" 0 "$?"

ln -s "$(command -v bash)" "$str_nonode/bash"
str_out="$(PATH="$str_nonode" "$str_nonode/bash" "$GATE" "$str_proj" 2>&1)"
expect "a missing node binary exits 2" 2 "$?"
has_text "a missing node binary is named as such" "node is required" "$str_out"

str_noperl="$(mktemp -d)"
ln -s "$(command -v bash)" "$str_noperl/bash"
ln -s "$(command -v node)" "$str_noperl/node"
str_out="$(PATH="$str_noperl" "$str_noperl/bash" "$GATE" "$str_proj" 2>&1)"
expect "a missing perl binary exits 2" 2 "$?"
has_text "a missing perl binary is named as such" "perl is required" "$str_out"
rm -rf "$str_noperl"

printf '{not json' >"$str_bad/package.json"
bash "$GATE" "$str_bad" >/dev/null 2>&1
expect "invalid package.json exits 2, not the doc-failure code" 2 "$?"
bash "$GATE" "$str_bad/missing" >/dev/null 2>&1
expect "missing package.json exits 2" 2 "$?"

printf 'Run `npm run build`.\n' >"$str_proj/README.md"
chmod 000 "$str_proj/README.md"
if [ "$(id -u)" -ne 0 ]; then
	bash "$GATE" "$str_proj" >/dev/null 2>&1
	expect "an unreadable doc fails instead of passing" 1 "$?"
fi
chmod 644 "$str_proj/README.md"

printf 'Run `npm run ghost -w app` or `npm run ghost --workspace=app`.\n' >"$str_proj/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a workspace selector after the script name is skipped" 0 "$?"
printf 'Run `npm run ghost -- -w app` and `npm run build -w app`.\n' >"$str_proj/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a workspace command does not hide a root command on the same line" 1 "$?"
printf 'Run `npm run ghost` and `npm run build -w app`.\n' >"$str_proj/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a selector in the next backticked command does not exempt this one" 1 "$?"
printf 'Run `npm run ghost -w app` and `npm run build -w app`.\n' >"$str_proj/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "two backticked commands each with their own selector are skipped" 0 "$?"
printf 'Run `npm run ghost --workspaces` and `npm run ghost -ws`.\n' >"$str_proj/README.md"
bash "$GATE" "$str_proj" >/dev/null 2>&1
expect "a selector at the end of a command is skipped" 0 "$?"
printf 'Run `npm run build`.\n' >"$str_proj/README.md"

if [ "$(id -u)" -ne 0 ]; then
	mkdir -p "$str_proj/docs/locked"
	chmod 000 "$str_proj/docs/locked"
	bash "$GATE" "$str_proj" >/dev/null 2>&1
	expect "a docs directory that cannot be traversed exits 2" 2 "$?"
	chmod 755 "$str_proj/docs/locked"
fi

str_badperl="$(mktemp -d)"
printf '#!/bin/sh\nexit 3\n' >"$str_badperl/perl"
chmod +x "$str_badperl/perl"
for str_t in bash node grep sort find; do ln -s "$(command -v "$str_t")" "$str_badperl/$str_t"; done
printf 'Run `npm run build`.\n' >"$str_proj/README.md"
str_out="$(PATH="$str_badperl" "$str_badperl/bash" "$GATE" "$str_proj" 2>&1)"
expect "a failing perl stage exits 2 instead of passing" 2 "$?"
has_text "a failing perl stage is reported as an extraction failure" "extracting npm commands" "$str_out"
rm -rf "$str_badperl"

[ "$int_failures" -eq 0 ]

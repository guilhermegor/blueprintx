#!/usr/bin/env bash

set -uo pipefail

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${BARREL_PROJECT:-}"
int_failures=0
WORK=""
INDEX=""
SNAPSHOT=""

cleanup() {
	[ -n "$SNAPSHOT" ] && cp "$SNAPSHOT" "$INDEX"
	rm -f "$SNAPSHOT"
	rm -rf "$WORK"
}
trap cleanup EXIT

if [ -z "$PROJECT" ]; then
	WORK="$(mktemp -d)"
	GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/bin/scaffold/ts_lib.sh" "$WORK" barrel-probe "probe" </dev/null >/dev/null 2>&1 || exit 1
	PROJECT="$WORK/barrel-probe"
	(cd "$PROJECT" && npm ci >/dev/null 2>&1) || exit 1
fi

INDEX="$PROJECT/src/index.ts"
SNAPSHOT="$(mktemp)"
cp "$INDEX" "$SNAPSHOT"

lint_barrel() {
	(cd "$PROJECT" && npx eslint src/index.ts >/dev/null 2>&1)
}

expect() {
	local str_desc="$1" int_want="$2"
	lint_barrel
	if [ "$?" -eq "$int_want" ]; then
		printf 'ok   %s\n' "$str_desc"
	else
		printf 'FAIL %s\n' "$str_desc"
		int_failures=$((int_failures + 1))
	fi
}

expect "shipped barrel is sorted and passes" 0

printf "export { NULL_EMITTER } from './utils/log-emitter.js';\nexport { greet } from './example.js';\n" >"$INDEX"
expect "unsorted barrel fails lint" 1

printf "export { greet } from './example.js';\nexport { NULL_EMITTER } from './utils/log-emitter.js';\n" >"$INDEX"
expect "sorted barrel passes lint" 0

[ "$int_failures" -eq 0 ] || { printf '%d check(s) failed\n' "$int_failures"; exit 1; }
printf 'all ts-lib barrel checks passed\n'

#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/templates/ts-lib/.github/workflows/pack-smoke.yml"
int_failures=0

check() {
	local str_desc="$1" str_pattern="$2"
	if grep -qF -- "$str_pattern" "$WORKFLOW"; then
		printf 'ok   %s\n' "$str_desc"
	else
		printf 'FAIL %s (missing: %s)\n' "$str_desc" "$str_pattern"
		int_failures=$((int_failures + 1))
	fi
}

check_absent() {
	local str_desc="$1" str_regex="$2"
	if grep -qE -- "$str_regex" "$WORKFLOW"; then
		printf 'FAIL %s (found: %s)\n' "$str_desc" "$str_regex"
		int_failures=$((int_failures + 1))
	else
		printf 'ok   %s\n' "$str_desc"
	fi
}

check "rehearsal bumps to a run-unique prerelease" '-rehearsal.${GITHUB_RUN_ID}.${GITHUB_RUN_ATTEMPT}'
check "build metadata is stripped before the suffix" 'base="${base%%+*}"'
check "version bump skips lifecycle scripts" 'npm version --no-git-tag-version --ignore-scripts'
check "publish uses a non-latest dist-tag" 'npm publish --tag rehearsal'
check "consumer installs the exact rehearsal version" 'npm install "$pkg_name@$REHEARSAL_VERSION"'
check "installed version is asserted against the rehearsal version" '[ "$installed" = "$REHEARSAL_VERSION" ]'
check_absent "no bare-name install from Verdaccio" 'npm (i|install) "?\$\{?pkg_name\}?"?([[:space:]]|$)'

[ "$int_failures" -eq 0 ] || { printf '%d check(s) failed\n' "$int_failures"; exit 1; }
printf 'all pack-smoke shape checks passed\n'

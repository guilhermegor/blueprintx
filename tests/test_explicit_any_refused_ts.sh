#!/usr/bin/env bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')
export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot
export GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL: $1"
	int_failures=$((int_failures + 1))
}

skeleton_scaffold() {
	grep '^scaffold=' "$REPO_ROOT/templates/$1/skeleton.meta" | cut -d= -f2-
}

scaffold_tier() {
	local str_name="$1" str_work="$2"
	local str_scaffold
	str_scaffold="$(skeleton_scaffold "$str_name")"
	if spec_skeleton_supported "$str_name"; then
		spec_stdin_for_skeleton "$str_name" "" \
			| BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
				"$str_work" project "CI explicit-any witness" "0.0.1" >/dev/null 2>&1
	else
		GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
			"$str_work" project "CI explicit-any witness" "0.0.1" \
			< <(printf '\n%.0s' {1..100}) >/dev/null 2>&1
	fi
}

install_tier() {
	if [ -f package-lock.json ]; then
		npm ci --no-audit --no-fund --ignore-scripts >/dev/null 2>&1
	else
		npm install --no-audit --no-fund --ignore-scripts >/dev/null 2>&1
	fi
}

expect_lint_refuses() {
	local str_name="$1" str_label="$2" str_file="$3" str_content="$4" str_rule="$5"
	local str_out
	printf '%s\n' "$str_content" >"$str_file"
	str_out="$(npm run lint 2>&1)"
	local int_rc=$?
	rm -f "$str_file"
	if [ "$int_rc" -eq 0 ]; then
		fail "$str_name: lint passed on $str_label"
	elif ! grep -qF -- "$str_rule" <<<"$str_out"; then
		fail "$str_name: lint failed on $str_label, but not under $str_rule"
	else
		pass "$str_name: lint refuses $str_label ($str_rule)"
	fi
}

check_tier() {
	local str_name="$1" str_project="${2:-}"
	if [ -z "$str_project" ]; then
		if ! scaffold_tier "$str_name" "$WORK_DIR/$str_name"; then
			fail "$str_name: scaffold failed"
			return
		fi
		str_project="$WORK_DIR/$str_name/project"
		(cd "$str_project" && install_tier) || {
			fail "$str_name: npm install failed"
			return
		}
	fi
	cd "$str_project" || return
	if ! npm run lint >/dev/null 2>&1; then
		fail "$str_name: lint is not clean before the witness is planted"
		return
	fi
	pass "$str_name: lint is clean before the witness is planted"
	expect_lint_refuses "$str_name" "an explicit any" \
		src/planted-any.ts 'export const planted: any = null;' '@typescript-eslint/no-explicit-any'
	expect_lint_refuses "$str_name" "a warning (--max-warnings 0)" \
		src/planted-warning.ts 'function unusedProbe(): void {}' '@typescript-eslint/no-unused-vars'
}

main() {
	local -a list_tiers=(ts-lib react-spa-webpack)
	if [ "$#" -ge 1 ]; then
		list_tiers=("$1")
	fi
	local str_tier
	for str_tier in "${list_tiers[@]}"; do
		check_tier "$str_tier" "${2:-}"
	done
	[ "$int_failures" -eq 0 ] || {
		echo "$int_failures case(s) failed"
		exit 1
	}
	echo "all cases passed"
}

main "$@"

#!/usr/bin/env bash
# pymarkdownlnt over every tracked .md file, root + templates/ — a MEASURED rule set, not
# the tool's default (blueprintx#383). Full measured counts and the tool-choice comparison
# (pymarkdownlnt vs markdownlint-cli2) live in the blueprintx#383 PR body, not here.
#
# Rules are chosen in .pymarkdown.json: MD018/019/020/021/023 (malformed-heading family),
# MD047, MD009. MD013/MD040 are deliberately OFF — both fired on the bulk of this repo's
# prose in the initial measurement, the same "a number nobody pays" shape
# check_complexity.sh's own history warns about.
#
# SCAFFOLD SIDE: deliberately NOT shipped into templates/python-common/ or any generated
# project. Same shape as check_actions.sh — templates/**/*.md is text this gate can already
# audit from BlueprintX's own root, so a generated project does not get its own copy.
#
# Resolve, don't install: a missing pymarkdownlnt is a graceful skip locally; CI sets
# MARKDOWNLINT_REQUIRED=1 to hard-fail there — a skip in CI is a gate reporting its own
# blindness as OK (same contract as check_actions.sh / check_secrets.sh).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CONFIG_FILE="$REPO_ROOT/.pymarkdown.json"

main() {
	local -a list_files
	mapfile -t list_files < <(git ls-files '*.md' | sort -u)

	# Fail on zero matches — a wrapper whose discovery matched nothing reports success
	# forever, green precisely because it checks nothing.
	if [ "${#list_files[@]}" -eq 0 ]; then
		echo "no tracked .md files discovered — the gate below would pass vacuously" >&2
		exit 1
	fi

	if ! command -v pymarkdown >/dev/null 2>&1; then
		if [ "${MARKDOWNLINT_REQUIRED:-0}" = "1" ]; then
			echo "pymarkdownlnt is required here but absent — a skipped gate in CI is a gate reporting its own blindness as OK" >&2
			exit 1
		fi
		echo "skip: pymarkdownlnt not installed locally (pip install pymarkdownlnt)"
		exit 0
	fi

	echo "pymarkdownlnt: ${#list_files[@]} tracked .md file(s)"

	if ! pymarkdown --strict-config --config "$CONFIG_FILE" scan "${list_files[@]}"; then
		echo "pymarkdownlnt found markdown problems (see above) — only MD018/019/020/021/023, MD047, MD009 are enabled; see .pymarkdown.json" >&2
		exit 1
	fi

	echo "pymarkdownlnt OK"
}

main "$@"

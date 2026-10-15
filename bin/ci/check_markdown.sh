#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CONFIG_FILE="$REPO_ROOT/.pymarkdown.json"

main() {
	local -a list_files
	mapfile -t list_files < <(git ls-files '*.md' | sort -u)

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

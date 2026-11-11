#!/bin/bash

set -euo pipefail

STR_ROOT="${1:-.}"
STR_PKG="$STR_ROOT/package.json"

[ -f "$STR_PKG" ] || {
	echo "check_doc_commands: $STR_PKG not found" >&2
	exit 2
}

list_docs() {
	local str_f
	for str_f in README.md CLAUDE.md AGENTS.md CONTRIBUTING.md; do
		[ -f "$STR_ROOT/$str_f" ] && printf '%s\n' "$STR_ROOT/$str_f"
	done
	[ -d "$STR_ROOT/docs" ] && find "$STR_ROOT/docs" -type f -name '*.md' | sort
	return 0
}

str_scripts="$(node -e 'console.log(Object.keys(require(process.argv[1]).scripts || {}).join("\n"))' "$(cd "$STR_ROOT" && pwd)/package.json")"

int_fail=0
while IFS= read -r str_doc; do
	[ -n "$str_doc" ] || continue
	while IFS= read -r str_hit; do
		str_name="${str_hit##* }"
		if ! printf '%s\n' "$str_scripts" | grep -qxF -- "$str_name"; then
			echo "check_doc_commands: $str_doc documents 'npm run $str_name' but package.json has no such script" >&2
			int_fail=1
		fi
	done < <(grep -v 'doc-commands:optional' "$str_doc" | grep -oE 'npm run [a-z0-9:_-]+' | sort -u || true)
done < <(list_docs)

exit "$int_fail"

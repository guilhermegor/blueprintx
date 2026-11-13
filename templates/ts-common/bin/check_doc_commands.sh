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
		if [ -f "$STR_ROOT/$str_f" ]; then printf '%s\n' "$STR_ROOT/$str_f"; fi
	done
	if [ -d "$STR_ROOT/docs" ]; then
		find "$STR_ROOT/docs" -type f -name '*.md' -not -path '*/node_modules/*' | sort
	fi
}

extract_hits() {
	local -a list_status=()
	grep -v 'doc-commands:optional' "$1" | perl -pe 's/npm run(?= +(?:(?!npm run)(?:[^- `][^ `]*|-[^- `][^ `]*|--[^ `]+) +)*?(?:-w|-ws|--workspaces?|--prefix)(?!=false\b)(?:[ =`]|$))//g' | grep -oE '(^|[^[:alnum:]])npm run( +--loglevel +[^ ]+| +--?[A-Za-z][A-Za-z-]*(=[^ ]*)?)* +[A-Za-z0-9_]([A-Za-z0-9:._-]*[A-Za-z0-9])?' | sort -u || list_status=("${PIPESTATUS[@]}")
	[ "${#list_status[@]}" -eq 0 ] && return 0
	[ "${list_status[0]}" -le 1 ] && [ "${list_status[1]}" -eq 0 ] &&
		[ "${list_status[2]}" -le 1 ] && [ "${list_status[3]}" -eq 0 ]
}

command -v node >/dev/null || {
	echo "check_doc_commands: node is required to read package.json" >&2
	exit 2
}

command -v perl >/dev/null || {
	echo "check_doc_commands: perl is required to parse npm commands" >&2
	exit 2
}

str_scripts="$(node -e 'console.log(Object.keys(require(process.argv[1]).scripts || {}).join("\n"))' "$(cd "$STR_ROOT" && pwd)/package.json")" || {
	echo "check_doc_commands: $STR_PKG is not valid JSON" >&2
	exit 2
}

str_docs="$(list_docs)" || {
	echo "check_doc_commands: document discovery failed under $STR_ROOT/docs" >&2
	exit 2
}

int_fail=0
while IFS= read -r str_doc; do
	[ -n "$str_doc" ] || continue
	[ -r "$str_doc" ] || {
		echo "check_doc_commands: cannot read $str_doc" >&2
		int_fail=1
		continue
	}
	str_hits="$(extract_hits "$str_doc")" || {
		echo "check_doc_commands: extracting npm commands from $str_doc failed" >&2
		exit 2
	}
	while IFS= read -r str_hit; do
		[ -n "$str_hit" ] || continue
		str_name="${str_hit##* }"
		if ! grep -qxF -- "$str_name" <<<"$str_scripts"; then
			echo "check_doc_commands: $str_doc documents 'npm run $str_name' but package.json has no such script" >&2
			int_fail=1
		fi
	done <<<"$str_hits"
done <<<"$str_docs"

exit "$int_fail"

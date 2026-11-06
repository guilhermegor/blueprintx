#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${PINS_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

AWK_SCAN='
function strip_comment(str_l) {
	sub(/(^|[[:space:]])#.*$/, "", str_l)
	return str_l
}
function find_key(str_l, str_k, re_k) {
	re_k = "[\"\047]?(" str_k ")[\"\047]?[[:space:]]*:"
	if (match(str_l, "^[[:space:]]*(-[[:space:]]+)*" re_k)) { bool_flow = 0; return 1 }
	if (match(str_l, "[{,][[:space:]]*" re_k) && index(substr(str_l, 1, RSTART), "{")) { bool_flow = 1; return 1 }
	return 0
}
function report(str_reason) {
	print FILENAME ":" FNR ": [" str_reason "] " $0
}
function check(str_value, bool_floats, str_plain) {
	if (str_value ~ /(^|[^A-Za-z0-9._-])[0-9]+\.[0-9]+\.[0-9]+/) { report("patch pin"); return }
	if (!bool_floats) return
	str_plain = str_value
	gsub(/"[^"]*"|\047[^\047]*\047/, "", str_plain)
	gsub(/\[|\]|,/, " ", str_plain)
	if (str_plain ~ /(^|[[:space:]])[0-9]+\.[0-9]*0($|[[:space:]])/) report("unquoted float, YAML drops the zero; quote it")
}
FNR == NR {
	str_line = strip_comment($0)
	if (find_key(str_line, "python-version")) {
		str_rest = substr(str_line, RSTART + RLENGTH)
		while (match(str_rest, /\$\{\{[[:space:]]*(env|matrix|inputs)\.[A-Za-z0-9_-]+/)) {
			str_name = substr(str_rest, RSTART, RLENGTH)
			sub(/.*\./, "", str_name)
			str_names = str_names "|" str_name
			str_rest = substr(str_rest, RSTART + RLENGTH)
		}
	}
	next
}
FNR == 1 { in_list = 0; in_block = 0; in_decl = 0 }
{
	str_line = strip_comment($0)
	match(str_line, /^[[:space:]]*/)
	int_lead = RLENGTH
	str_parent = ""
	for (int_i = int_lead - 1; int_i >= 0; int_i--) if (int_i in arr_key) { str_parent = arr_key[int_i]; break }
	if (str_line !~ /^[[:space:]]*$/) {
		for (int_i in arr_key) if (int_i + 0 >= int_lead) delete arr_key[int_i]
		if (match(str_line, /^[[:space:]]*[A-Za-z0-9_-]+:[[:space:]]*$/)) { str_k = str_line; gsub(/[[:space:]:]/, "", str_k); arr_key[int_lead] = str_k }
	}
	if (in_block) {
		if (str_line ~ /^[[:space:]]*$/ || int_lead > int_indent) { check(str_line, 0); next }
		in_block = 0
	}
	if (in_list) {
		if (str_line ~ /^[[:space:]]*(-|$)/) { check(str_line, 1); next }
		in_list = 0
	}
	if (in_decl) {
		if (str_line !~ /^[[:space:]]*$/ && int_lead <= int_decl) in_decl = 0
		else if (str_line ~ /^[[:space:]]*default[[:space:]]*:/) check(substr(str_line, index(str_line, ":") + 1), 1)
	}
	if (find_key(str_line, "python-version-file")) report("python-version-file cannot be verified; use python-version")
	bool_hit = find_key(str_line, "python-version")
	if (!bool_hit && str_names != "" && str_parent ~ /^(matrix|include|env|inputs)$/) bool_hit = find_key(str_line, substr(str_names, 2))
	if (bool_hit) {
		str_rest = substr(str_line, RSTART + RLENGTH)
		if (str_rest ~ /\$\{\{[[:space:]]*vars\./) report("vars.* is resolved outside the repository and cannot be verified")
		if (bool_flow) {
			if (str_rest ~ /^[[:space:]]*\[/) sub(/\].*$/, "", str_rest)
			else sub(/[,}].*$/, "", str_rest)
			check(str_rest, 1)
			next
		}
		match(str_line, /^[[:space:]]*(-[[:space:]]+)*/)
		int_indent = RLENGTH
		if (str_rest ~ /^[[:space:]]*$/) { in_list = 1; in_decl = 1; int_decl = int_indent }
		else if (str_rest ~ /^[[:space:]]*[|>][-+]?[[:space:]]*$/) in_block = 1
		else {
			in_block = 1
			if (str_rest ~ /^[[:space:]]*\[/) sub(/\].*$/, "", str_rest)
			else sub(/[,}].*$/, "", str_rest)
			check(str_rest, 1)
		}
	}
}
'

list_candidates() {
	local str_top
	str_top="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
	if [ "$str_top" = "$(cd "$REPO_ROOT" && pwd -P)" ]; then
		env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard -- .github/workflows templates
		return
	fi
	(cd "$REPO_ROOT" && find .github/workflows templates \
		-name node_modules -prune -o \
		-path '*.github/workflows/*' \( -name '*.yml' -o -name '*.yaml' \) -print0)
}

collect_workflows() {
	local str_found
	local str_err
	local str_f
	str_found="$(mktemp)"
	str_err="$(mktemp)"
	list_candidates >"$str_found" 2>"$str_err" || { cat "$str_err" >&2; rm -f "$str_found" "$str_err"; exit 1; }
	if [ -s "$str_err" ]; then
		cat "$str_err" >&2
		rm -f "$str_found" "$str_err"
		exit 1
	fi
	rm -f "$str_err"
	while IFS= read -r -d '' str_f; do
		case "$str_f" in
		*/node_modules/*) continue ;;
		.github/workflows/*.yml | .github/workflows/*.yaml | */.github/workflows/*.yml | */.github/workflows/*.yaml) ;;
		*) continue ;;
		esac
		if [ -f "$REPO_ROOT/$str_f" ]; then echo "$REPO_ROOT/$str_f"; fi
	done <"$str_found"
	rm -f "$str_found"
}

main() {
	local -a list_files=()
	local -a list_awk
	local str_hits=""
	local str_out
	local str_dir
	local str_f
	read -r -a list_awk <<<"${PINS_AWK:-awk}"
	for str_dir in "$REPO_ROOT/.github/workflows" "$REPO_ROOT/templates"; do
		if [ ! -d "$str_dir" ]; then
			echo "Missing $str_dir; refusing a partial scan." >&2
			exit 1
		fi
	done
	local str_list
	str_list="$(collect_workflows)"
	while IFS= read -r str_f; do
		if [ -n "$str_f" ]; then list_files+=("$str_f"); fi
	done <<<"$str_list"
	if [ "${#list_files[@]}" -eq 0 ]; then
		echo "No workflow files found under $REPO_ROOT; refusing to pass vacuously." >&2
		exit 1
	fi
	for str_f in "${list_files[@]}"; do
		str_out="$("${list_awk[@]}" "$AWK_SCAN" "$str_f" "$str_f")"
		[ -z "$str_out" ] || str_hits="${str_hits}${str_hits:+$'\n'}${str_out}"
	done
	if [ -n "$str_hits" ]; then
		echo "python-version must be a literal minor-level pin (no patch, no dropped-zero float, no file or vars.* indirection):" >&2
		printf '%s\n' "$str_hits" | sed 's/^/    /' >&2
		exit 1
	fi
	echo "workflow python-version pins OK (minor-level only, ${#list_files[@]} files scanned)."
}

main "$@"

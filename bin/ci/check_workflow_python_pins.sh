#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${PINS_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

AWK_SCAN='
function strip_comment(str_l) {
	sub(/(^|[[:space:]])#.*$/, "", str_l)
	return str_l
}
function blank_exprs(str_l, str_pad, int_j) {
	while (match(str_l, /\$\{\{[^}]*\}\}/)) {
		str_pad = ""
		for (int_j = 0; int_j < RLENGTH; int_j++) str_pad = str_pad " "
		str_l = substr(str_l, 1, RSTART - 1) str_pad substr(str_l, RSTART + RLENGTH)
	}
	return str_l
}
function nearest(int_below, int_j) {
	for (int_j = int_below - 1; int_j >= 0; int_j--) if (int_j in arr_key) return int_j
	return -1
}
function depth(str_l, int_o, int_c) {
	gsub(/"[^"]*"|\047[^\047]*\047/, "", str_l)
	int_o = gsub(/[{\[]/, "", str_l)
	int_c = gsub(/[}\]]/, "", str_l)
	return int_o - int_c
}
function expr_check(str_v) {
	gsub(/\$\{\{[[:space:]]*(env|matrix|inputs)\.[A-Za-z0-9_-]+[[:space:]]*\}\}/, "", str_v)
	if (str_v ~ /\$\{\{/) report("expression is resolved outside the repository and cannot be verified")
}
function find_key(str_l, str_k, re_k) {
	re_k = "[\"\047]?(" str_k ")[\"\047]?[[:space:]]*:"
	str_l = blank_exprs(str_l)
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
			str_space = str_name
			sub(/^\$\{\{[[:space:]]*/, "", str_space)
			sub(/\..*/, "", str_space)
			sub(/.*\./, "", str_name)
			arr_names[str_space] = arr_names[str_space] "|" str_name
			str_rest = substr(str_rest, RSTART + RLENGTH)
		}
	}
	next
}
FNR == 1 { in_list = 0; in_block = 0; in_decl = 0; in_opts = 0; bool_fl = 0; int_fd = 0 }
{
	str_line = strip_comment($0)
	match(str_line, /^[[:space:]]*/)
	int_lead = RLENGTH
	int_p = nearest(int_lead)
	int_gg = nearest(nearest(int_p))
	str_parent = (int_p >= 0) ? arr_key[int_p] : ""
	str_ggp = (int_gg >= 0) ? arr_key[int_gg] : ""
	if (str_line !~ /^[[:space:]]*$/) {
		for (int_i in arr_key) if (int_i + 0 >= int_lead) delete arr_key[int_i]
		if (match(str_line, /^[[:space:]]*[A-Za-z0-9_-]+:[[:space:]]*$/)) { str_k = str_line; gsub(/[[:space:]:]/, "", str_k); arr_key[int_lead] = str_k }
	}
	if (str_line ~ /GITHUB_ENV/ && ("env" in arr_names)) {
		int_n = split(arr_names["env"], arr_en, "|")
		for (int_e = 2; int_e <= int_n; int_e++) if (index(str_line, arr_en[int_e] "=")) { report("python-version fed through GITHUB_ENV cannot be verified"); break }
	}
	if (in_block) {
		if (str_line ~ /^[[:space:]]*$/ || int_lead > int_indent) {
			expr_check(str_line)
			str_c = str_line
			if (bool_fl && index(str_c, "]")) sub(/\].*$/, "", str_c)
			check(str_c, bool_fl)
			if (index(str_line, "]")) bool_fl = 0
			next
		}
		in_block = 0
		bool_fl = 0
	}
	if (in_list) {
		if (str_line ~ /^[[:space:]]*$/ || (str_line ~ /^[[:space:]]*-/ && int_lead >= int_lmin)) { expr_check(str_line); check(str_line, 1); next }
		in_list = 0
	}
	if (in_decl) {
		if (str_line !~ /^[[:space:]]*$/ && int_lead <= int_decl) { in_decl = 0; in_opts = 0 }
		else if (str_line ~ /^[[:space:]]*default[[:space:]]*:/) check(substr(str_line, index(str_line, ":") + 1), 1)
		else if (str_line ~ /^[[:space:]]*options[[:space:]]*:/) {
			str_o = substr(str_line, index(str_line, ":") + 1)
			if (str_o ~ /^[[:space:]]*$/) in_opts = 1
			else check(str_o, 1)
		}
		else if (in_opts) {
			if (str_line ~ /^[[:space:]]*-/) check(str_line, 1)
			else if (str_line !~ /^[[:space:]]*$/) in_opts = 0
		}
	}
	if (find_key(str_line, "python-version-file")) report("python-version-file cannot be verified; use python-version")
	str_space = str_parent
	if (str_space == "include") str_space = "matrix"
	if (str_parent == "with" && str_ggp == "jobs") str_space = "inputs"
	if (int_fd > 0) {
		str_space = str_fs
		int_fd += depth(str_line)
		if (int_fd < 0) int_fd = 0
	} else if (match(str_line, /(matrix|env|inputs)"?[[:space:]]*:[[:space:]]*[{\[]/)) {
		str_space = substr(str_line, RSTART, RLENGTH)
		sub(/[^a-z].*/, "", str_space)
		str_fs = str_space
		int_fd = depth(substr(str_line, RSTART + RLENGTH - 1))
		if (int_fd < 0) int_fd = 0
	}
	bool_hit = find_key(str_line, "python-version")
	if (!bool_hit && (str_space in arr_names)) bool_hit = find_key(str_line, substr(arr_names[str_space], 2))
	if (bool_hit) {
		str_rest = substr(str_line, RSTART + RLENGTH)
		expr_check(str_rest)
		bool_fl = 0
		if (bool_flow) {
			if (str_rest ~ /^[[:space:]]*\[/) sub(/\].*$/, "", str_rest)
			else sub(/[,}].*$/, "", str_rest)
			check(str_rest, 1)
			next
		}
		match(str_line, /^[[:space:]]*(-[[:space:]]+)*/)
		int_indent = RLENGTH
		if (str_rest ~ /^[[:space:]]*$/) { in_list = 1; in_decl = 1; int_decl = int_indent; int_lmin = (int_indent > int_lead) ? int_lead + 1 : int_lead }
		else if (str_rest ~ /^[[:space:]]*[|>][-+]?[[:space:]]*$/) in_block = 1
		else {
			in_block = 1
			bool_fl = (str_rest ~ /^[[:space:]]*\[/ && index(str_rest, "]") == 0)
			if (str_rest ~ /^[[:space:]]*\[/) sub(/\].*$/, "", str_rest)
			else sub(/[,}].*$/, "", str_rest)
			check(str_rest, 1)
		}
	}
}
'

git_clean() {
	local -a list_unset=()
	local str_var
	while IFS= read -r str_var; do list_unset+=(-u "$str_var"); done < <(compgen -e | grep '^GIT_' || true)
	env ${list_unset[@]+"${list_unset[@]}"} git "$@"
}

list_candidates() {
	local str_top
	str_top="$(git_clean -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
	if [ "$str_top" = "$(cd "$REPO_ROOT" && pwd -P)" ]; then
		git_clean -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard -- .github/workflows templates
		return
	fi
	(cd "$REPO_ROOT" && find .github/workflows templates \
		-name node_modules -prune -o \
		-path '*.github/workflows/*' \( -name '*.yml' -o -name '*.yaml' \) -print0)
}

collect_workflows() {
	local str_out="$1"
	local str_found
	local str_err
	local str_f
	str_found="$(mktemp)"
	str_err="$(mktemp)"
	list_candidates >"$str_found" 2>"$str_err" || { cat "$str_err" >&2; rm -f "$str_found" "$str_err"; exit 1; }
	if grep -qiE 'could not|denied|unable|cannot' "$str_err" || grep -qv '^warning: ' "$str_err"; then
		cat "$str_err" >&2
		rm -f "$str_found" "$str_err"
		exit 1
	fi
	cat "$str_err" >&2
	rm -f "$str_err"
	: >"$str_out"
	while IFS= read -r -d '' str_f; do
		case "$str_f" in
		*/node_modules/*) continue ;;
		.github/workflows/*.yml | .github/workflows/*.yaml | */.github/workflows/*.yml | */.github/workflows/*.yaml) ;;
		*) continue ;;
		esac
		if [ -f "$REPO_ROOT/$str_f" ]; then printf '%s\0' "$REPO_ROOT/$str_f" >>"$str_out"; fi
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
	str_list="$(mktemp)"
	collect_workflows "$str_list"
	while IFS= read -r -d '' str_f; do
		list_files+=("$str_f")
	done <"$str_list"
	rm -f "$str_list"
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

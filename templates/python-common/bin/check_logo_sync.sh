#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

ROOT="${1:-.}"

readme_logo() {
	grep -oE 'raw\.githubusercontent\.com/[^"]*/main/[^"]+' "$ROOT/README.md" 2>/dev/null |
		head -n 1 | sed -E 's#^.*/main/##' || true
}

index_logo() {
	grep -oE '<img[^>]*src="[^"]+"' "$ROOT/docs/index.md" 2>/dev/null |
		head -n 1 | sed -E 's#.*src="([^"]+)"#docs/\1#' || true
}

theme_logo() {
	local str_key="$1"
	sed -nE "s#^[[:space:]]+${str_key}:[[:space:]]*([^[:space:]]+)[[:space:]]*\$#docs/\1#p" \
		"$ROOT/mkdocs.yml" 2>/dev/null | head -n 1 || true
}

main() {
	local -a list_labels=("README.md image" "docs/index.md image" "mkdocs.yml theme.logo"
		"mkdocs.yml theme.favicon")
	local -a list_paths=("$(readme_logo)" "$(index_logo)" "$(theme_logo logo)" "$(theme_logo favicon)")
	local int_status=0 int_i str_ref_path="" str_ref_label=""

	for int_i in "${!list_paths[@]}"; do
		if [[ -z "${list_paths[$int_i]}" ]]; then
			print_status "error" "${list_labels[$int_i]}: no logo reference found"
			int_status=1
		elif [[ ! -f "$ROOT/${list_paths[$int_i]}" ]]; then
			print_status "error" "${list_labels[$int_i]}: ${list_paths[$int_i]} does not exist"
			int_status=1
		elif [[ -z "$str_ref_path" ]]; then
			str_ref_path="${list_paths[$int_i]}"
			str_ref_label="${list_labels[$int_i]}"
		elif ! cmp -s "$ROOT/$str_ref_path" "$ROOT/${list_paths[$int_i]}"; then
			print_status "error" "${list_labels[$int_i]} (${list_paths[$int_i]}) differs from $str_ref_label ($str_ref_path)"
			int_status=1
		fi
	done

	if [[ "$int_status" -eq 0 ]]; then
		print_status "success" "README and docs logos are the same image"
	fi
	return "$int_status"
}

main

#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

PRECOMMIT_FILE="$REPO_ROOT/.pre-commit-config.yaml"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"
CI_SCRIPTS_DIR="$REPO_ROOT/bin/ci"
EXEMPTIONS_FILE="$REPO_ROOT/bin/precommit_ci_parity_exemptions.txt"

precommit_scripts() {
	grep -oE '^[[:space:]]*entry:.*' "$PRECOMMIT_FILE" | grep -oE '[^[:space:]]+\.(sh|py)' | xargs -n1 basename | sort -u
}

ci_dir_scripts() {
	find "$CI_SCRIPTS_DIR" -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) -exec basename {} \; | sort -u
}

script_in_any_workflow() {
	local -a list_files
	mapfile -t list_files < <(find "$WORKFLOWS_DIR" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \))
	[ "${#list_files[@]}" -gt 0 ] || return 1
	local str_escaped str_body
	str_escaped="$(printf '%s' "$1" | sed 's/[][\.*^$(){}?+|/]/\\&/g')"
	str_body="$(sed 's/#.*//' "${list_files[@]}")"
	grep -qE "(^|[[:space:]]|[;&|(]|/)${str_escaped}([[:space:]]|[;&|)]|$)" <<<"$str_body"
}

validate_exemptions() {
	[ -f "$EXEMPTIONS_FILE" ] || return 0
	local str_script str_side str_reason int_line=0 int_bad=0
	while IFS='|' read -r str_script str_side str_reason; do
		int_line=$((int_line + 1))
		[[ "$str_script" =~ ^[[:space:]]*(#.*)?$ ]] && continue
		if [ -z "$str_reason" ]; then
			print_status "error" "exemption for '$str_script' ($str_side) has no reason — rejected"
			int_bad=$((int_bad + 1))
			continue
		fi
		case "$str_side" in
		precommit_only | ci_only) ;;
		*)
			print_status "error" "exemptions line $int_line: invalid side '$str_side' (expected precommit_only|ci_only)"
			int_bad=$((int_bad + 1))
			;;
		esac
	done <"$EXEMPTIONS_FILE"
	[ "$int_bad" -eq 0 ] || exit 1
}

exemption_reason() {
	local str_script="$1" str_side="$2"
	[ -f "$EXEMPTIONS_FILE" ] || return 0
	while IFS='|' read -r str_line_script str_line_side str_line_reason; do
		[[ "$str_line_script" =~ ^[[:space:]]*(#.*)?$ ]] && continue
		if [ "$str_line_script" = "$str_script" ] && [ "$str_line_side" = "$str_side" ]; then
			if [ -z "$str_line_reason" ]; then
				print_status "error" "exemption for '$str_script' ($str_side) has no reason — rejected"
				exit 1
			fi
			echo "$str_line_reason"
			return 0
		fi
	done <"$EXEMPTIONS_FILE"
	return 0
}

discover_candidates() {
	local -a list_precommit
	mapfile -t list_precommit < <(precommit_scripts)
	{
		[ "${#list_precommit[@]}" -gt 0 ] && printf '%s\n' "${list_precommit[@]}"
		ci_dir_scripts
		[ -f "$REPO_ROOT/bin/check_makefile_pairing.sh" ] && echo "check_makefile_pairing.sh"
		true
	} | sort -u | sed '/^$/d'
}

classify_script() {
	local str_script="$1" is_precommit="$2" is_ci str_reason str_side str_msg
	is_ci=false
	script_in_any_workflow "$str_script" && is_ci=true

	if [ "$is_precommit" = true ] && [ "$is_ci" = false ]; then
		str_side="precommit_only"
		str_msg="$str_script runs in pre-commit but no CI workflow references it"
	elif [ "$is_precommit" = false ] && [ "$is_ci" = true ]; then
		str_side="ci_only"
		str_msg="$str_script runs in CI but no pre-commit hook references it"
	else
		echo "ok"
		return 0
	fi

	str_reason="$(exemption_reason "$str_script" "$str_side")"
	if [ -n "$str_reason" ]; then
		echo "exempt $str_reason"
	else
		echo "fail $str_msg"
	fi
}

main() {
	[ -f "$PRECOMMIT_FILE" ] || { print_status "error" "missing $PRECOMMIT_FILE"; exit 1; }
	[ -d "$WORKFLOWS_DIR" ] || { print_status "error" "missing $WORKFLOWS_DIR"; exit 1; }
	validate_exemptions

	local -a list_precommit list_candidates
	mapfile -t list_precommit < <(precommit_scripts)
	mapfile -t list_candidates < <(discover_candidates)

	if [ "${#list_candidates[@]}" -eq 0 ]; then
		print_status "error" "discovered ZERO candidate scripts — discovery is broken, not the tree"
		exit 1
	fi

	local str_script is_precommit str_p str_verdict
	local int_checked=0 int_exempted=0 int_failures=0

	for str_script in "${list_candidates[@]}"; do
		int_checked=$((int_checked + 1))
		is_precommit=false
		for str_p in "${list_precommit[@]}"; do
			[ "$str_p" = "$str_script" ] && is_precommit=true && break
		done

		str_verdict="$(classify_script "$str_script" "$is_precommit")"
		case "$str_verdict" in
		exempt\ *)
			int_exempted=$((int_exempted + 1))
			print_status "info" "exempted: $str_script — ${str_verdict#exempt }"
			;;
		fail\ *)
			int_failures=$((int_failures + 1))
			print_status "error" "${str_verdict#fail }"
			;;
		esac
	done

	if [ "$int_failures" -ne 0 ]; then
		print_status "error" \
			"check_precommit_ci_parity: $int_failures unexplained mismatch(es) across $int_checked script(s)"
		exit 1
	fi
	print_status "success" \
		"check_precommit_ci_parity: $int_checked script(s) compared, $int_exempted exempted, 0 unexplained mismatches"
}

main "$@"

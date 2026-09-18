#!/usr/bin/env bash
# Verifies pre-commit and CI run the SAME checks, in both directions (blueprintx#384).
#
# CLAUDE.md claims this as prose ("the shared checks live in bin/ci/*.sh ... and both the
# workflow and the hook call them"). Nothing checked it, so nothing would report it becoming
# false. This script makes it a measured property instead.
#
# ⚠️ Join key is the INVOKED SCRIPT, never a hook id or job name. The two sides express a
# check differently (one pre-commit hook id vs. one-or-many CI job/step names), so a
# name-keyed comparison is blind — see blueprintx#384's own measurement (51 pre-commit hooks
# vs. 1 CI job with 31 steps on the scaffold side). A hook's `entry:` and a CI step's `run:`
# both name the same script file; that is the only key both sides genuinely share.
#
# ⚠️ Scans EVERY workflow file under .github/workflows/, not just scaffold_checks.yml.
# bin/check_secrets.sh looks pre-commit-only from scaffold_checks.yml alone — it actually
# runs in CI from secret_scan.yml. A single-file read reports a gap that does not exist.
#
# Candidate scripts = every script named in .pre-commit-config.yaml's local hooks, union
# every script physically in bin/ci/ (the directory CLAUDE.md names as the shared-check
# home), union bin/check_makefile_pairing.sh (documented as living outside bin/ci/ on
# purpose). This is deliberately narrower than "every script any workflow happens to run" —
# pr_reconcile.sh, enable_repo_rules.sh, rerun_stale_gate_runs.sh and similar are repo
# automation, not checks with a pre-commit/CI parity expectation, and were never candidates
# for a local mirror.
#
# A finding is not automatically a failure: bin/precommit_ci_parity_exemptions.txt is data,
# not logic (same shape as .review-bots.yaml / .layer-policy.yaml) — every entry names a
# script, a side, and a REQUIRED reason. An exemption with no reason is itself rejected.
#
# Usage: bash bin/check_precommit_ci_parity.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

PRECOMMIT_FILE="$REPO_ROOT/.pre-commit-config.yaml"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"
CI_SCRIPTS_DIR="$REPO_ROOT/bin/ci"
EXEMPTIONS_FILE="$REPO_ROOT/bin/precommit_ci_parity_exemptions.txt"

# Every script named by a `entry:` line in .pre-commit-config.yaml, basename only. The
# pattern matches the script wherever it sits in the entry (after `bash`/`python3`, before
# any `--root .` argument) — entries are never plain hook ids, only local hooks have entry:.
precommit_scripts() {
	grep -oE '^[[:space:]]*entry:.*' "$PRECOMMIT_FILE" | grep -oE '[^[:space:]]+\.(sh|py)' | xargs -n1 basename | sort -u
}

# Every *.sh / *.py physically in bin/ci/ — the shared-check directory CLAUDE.md names.
ci_dir_scripts() {
	find "$CI_SCRIPTS_DIR" -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) -exec basename {} \; | sort -u
}

# Does $1 (a script basename) appear anywhere in any workflow file's text? Broad on purpose:
# a multi-line `run: |` block scalar is still plain text, and this must not miss it.
script_in_any_workflow() {
	local -a list_files
	mapfile -t list_files < <(find "$WORKFLOWS_DIR" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \))
	[ "${#list_files[@]}" -gt 0 ] || return 1
	# INVOCATION, never mere presence: strip YAML comments first, then require the name
	# to sit at a command position. A workflow comment naming a script used to set
	# is_ci=true and pass the parity check for a script CI never runs — and this repo's
	# workflows are full of such prose, including a comment about parity itself.
	# Stripping can only ever hide a match, so the failure direction stays closed.
	local str_escaped str_body
	str_escaped="$(printf '%s' "$1" | sed 's/[][\.*^$(){}?+|/]/\\&/g')"
	# ⚠️ Read into a variable and match with a HERE-STRING, never `sed … | grep -q`.
	# `grep -q` exits at the first match and closes the pipe, `sed` then dies of SIGPIPE,
	# and `set -o pipefail` reports the pipeline as 141 — so a script that IS invoked
	# reads as absent. It only shows up on inputs big enough that sed is still writing:
	# a small fixture passes and the real workflow file fails (measured, 17 false
	# mismatches across 24 scripts).
	str_body="$(sed 's/#.*//' "${list_files[@]}")"
	grep -qE "(^|[[:space:]]|[;&|(]|/)${str_escaped}([[:space:]]|[;&|)]|$)" <<<"$str_body"
}

# $1 = script basename, $2 = "precommit_only" | "ci_only". Prints the reason on a match,
# nothing on no match. Fails loudly on a reason-less entry — a bare name is not an exemption.
# Validate the WHOLE exemptions file up front, independently of whether any entry is
# needed this run. exemption_reason() below is only reached on a current mismatch, so a
# malformed or stale entry sits unread for as long as the mismatch it excuses does not
# occur — reading as deliberate policy while doing nothing, until the day it matches the
# wrong thing. An exemption list consulted only on the failure path is never validated.
validate_exemptions() {
	[ -f "$EXEMPTIONS_FILE" ] || return 0
	local str_script str_side str_reason int_line=0 int_bad=0
	while IFS='|' read -r str_script str_side str_reason; do
		int_line=$((int_line + 1))
		[[ "$str_script" =~ ^[[:space:]]*(#.*)?$ ]] && continue
		if [ -z "$str_reason" ]; then
			# Same wording the per-entry path used, so the assertion that this is
			# REJECTED (rather than silently skipped) keeps testing the behaviour
			# regardless of which path now catches it.
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
		# ⚠️ `printf '%s\n' "${arr[@]}"` with an EMPTY array still runs the format once,
		# printing one blank line — guard it, or an empty pre-commit config silently
		# manufactures one phantom candidate and the zero-discovery check never fires
		# against a genuinely empty tree.
		[ "${#list_precommit[@]}" -gt 0 ] && printf '%s\n' "${list_precommit[@]}"
		ci_dir_scripts
		[ -f "$REPO_ROOT/bin/check_makefile_pairing.sh" ] && echo "check_makefile_pairing.sh"
		true
	} | sort -u | sed '/^$/d'
}

# Classify ONE script. Echoes "ok", "exempt <reason>" or "fail <message>"; the caller
# keeps the counters, so this stays a pure decision about a single name.
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

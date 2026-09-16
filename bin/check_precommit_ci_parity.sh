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
	grep -lF -- "$1" "${list_files[@]}" >/dev/null 2>&1
}

# $1 = script basename, $2 = "precommit_only" | "ci_only". Prints the reason on a match,
# nothing on no match. Fails loudly on a reason-less entry — a bare name is not an exemption.
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

main() {
	[ -f "$PRECOMMIT_FILE" ] || { print_status "error" "missing $PRECOMMIT_FILE"; exit 1; }
	[ -d "$WORKFLOWS_DIR" ] || { print_status "error" "missing $WORKFLOWS_DIR"; exit 1; }

	local -a list_precommit list_candidates
	mapfile -t list_precommit < <(precommit_scripts)
	mapfile -t list_candidates < <(
		{
			# ⚠️ `printf '%s\n' "${arr[@]}"` with an EMPTY array still runs the format once,
			# printing one blank line — guard it, or an empty pre-commit config silently
			# manufactures one phantom candidate and the zero-discovery check below never
			# fires against a genuinely empty tree.
			[ "${#list_precommit[@]}" -gt 0 ] && printf '%s\n' "${list_precommit[@]}"
			ci_dir_scripts
			[ -f "$REPO_ROOT/bin/check_makefile_pairing.sh" ] && echo "check_makefile_pairing.sh"
			true
		} | sort -u | sed '/^$/d'
	)

	if [ "${#list_candidates[@]}" -eq 0 ]; then
		print_status "error" "discovered ZERO candidate scripts — discovery is broken, not the tree"
		exit 1
	fi

	local str_script is_precommit is_ci str_reason str_p
	local int_checked=0 int_exempted=0 int_failures=0

	for str_script in "${list_candidates[@]}"; do
		int_checked=$((int_checked + 1))
		is_precommit=false
		for str_p in "${list_precommit[@]}"; do
			[ "$str_p" = "$str_script" ] && is_precommit=true && break
		done
		is_ci=false
		script_in_any_workflow "$str_script" && is_ci=true

		if [ "$is_precommit" = true ] && [ "$is_ci" = false ]; then
			str_reason="$(exemption_reason "$str_script" "precommit_only")"
			if [ -n "$str_reason" ]; then
				int_exempted=$((int_exempted + 1))
				print_status "info" "exempted (pre-commit only): $str_script — $str_reason"
			else
				int_failures=$((int_failures + 1))
				print_status "error" "$str_script runs in pre-commit but no CI workflow references it"
			fi
		elif [ "$is_precommit" = false ] && [ "$is_ci" = true ]; then
			str_reason="$(exemption_reason "$str_script" "ci_only")"
			if [ -n "$str_reason" ]; then
				int_exempted=$((int_exempted + 1))
				print_status "info" "exempted (CI only): $str_script — $str_reason"
			else
				int_failures=$((int_failures + 1))
				print_status "error" "$str_script runs in CI but no pre-commit hook references it"
			fi
		fi
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

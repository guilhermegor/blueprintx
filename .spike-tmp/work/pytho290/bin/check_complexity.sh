#!/bin/bash
#
# check_complexity.sh — cyclomatic-complexity ceiling, per tree.
#
# WHY THIS EXISTS, and why the number differs by tree:
#
#   | tree     | max | the argument                                                        |
#   |----------|-----|---------------------------------------------------------------------|
#   | tests/   |  1  | a test with a branch is testing two paths, and WHICH one ran does   |
#   |          |     | not appear in the green. Complexity 1 is the mechanical form of the |
#   |          |     | rule tests/CLAUDE.md already states in prose: "each test asserts    |
#   |          |     | one behaviour". Prose never enforced it; this does.                 |
#   | src/     |  2  | production code. Branching that is genuinely the work (a validator, |
#   |          |     | a parser) takes the escape hatch below WITH a reason, rather than   |
#   |          |     | being contorted to satisfy a number.                                |
#   | bin/     |  8  | the gates are parsing tools by nature — argv, ruff output, YAML,    |
#   |          |     | AST. Measured at 2 they were 74% violating, which is a number       |
#   |          |     | nobody pays and therefore a gate nobody keeps.                      |
#
# ⚠️ DO NOT REIMPLEMENT MCCABE. ruff is already a dependency and already ships the metric as
# C901. A hand-rolled counter is not merely redundant, it is WRONG in a way that silently
# invalidates the threshold: a draft counter that treated `assert` and `with` as decision
# points reported 85% of tests/ violating where the real figure was 8%. A threshold agreed
# against one implementation and enforced by another is not the threshold anybody agreed to.
#
# ⚠️ WHY TWO INVOCATIONS AND NOT ONE CONFIG. ruff's `per-file-ignores` can only switch a rule
# OFF for a path; it cannot give a path a different `max-complexity`. So the per-tree ceiling
# has to come from separate runs, one per threshold.
#
# Escape hatch: put `# complexity-ok: <reason>` on the `def` line (ruff anchors C901 there,
# not on a decorator). The reason is REQUIRED — a bare marker is rejected, because the point
# of the hatch is the sentence explaining why the branching is the work.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh" # resolve_python / resolve_poetry / run_poetry

# The ceiling per tree. This array IS the policy: adding a tree is adding a key, never a new
# branch below. Order is irrelevant; every entry gets its own ruff run.
declare -A DICT_MAX_COMPLEXITY=(
	["tests"]=1
	["src"]=2
	["bin"]=8
)

STR_ALLOW_MARKER="complexity-ok:"
# Upper bound on how far past the `def` the signature scan looks. A signature longer than this
# is its own problem; the bound stops a malformed file turning the scan into a file read.
_INT_SIGNATURE_SCAN_LINES=20
STR_ROOT="."
INT_FILES_SEEN=0

parse_args() {
	# Only --root is accepted, so BlueprintX can run THIS file over its own tree instead of
	# keeping a second copy (the treatment blueprintx#189 gave the function-length gate).
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--root)
			STR_ROOT="${2:-.}"
			shift 2
			;;
		*)
			print_status "error" "Unknown argument: $1 (only --root <dir> is accepted)"
			exit 2
			;;
		esac
	done
}

STR_RUFF_MODE=""

resolve_ruff() {
	# Set STR_RUFF_MODE to "poetry", "system", or "" (absent). Probed with --version so a
	# real lint exit code is never mistaken for "absent".
	#
	# ⚠️ SETS A GLOBAL, never prints for `$(resolve_ruff)`. `resolve_poetry` populates the
	# POETRY_CMD array, and command substitution runs in a SUBSHELL — so resolving there
	# leaves POETRY_CMD unset in the caller, every later `run_poetry` fails, and (with the
	# output suppressed, as it first was here) the gate reports a clean tree because it ran
	# nothing at all. Measured: 79 known violations, reported as success.
	STR_RUFF_MODE=""
	if resolve_poetry >/dev/null 2>&1 && run_poetry run ruff --version >/dev/null 2>&1; then
		STR_RUFF_MODE="poetry"
		return 0
	fi
	if command -v ruff >/dev/null 2>&1; then
		STR_RUFF_MODE="system"
	fi
}

run_ruff_c901() {
	# Emit ruff's concise C901 findings for one tree at one threshold.
	local str_dir="$1" int_max="$2"
	local str_stderr int_status
	local -a list_args=(
		check "$str_dir"
		--select C901
		--config "$SCRIPT_DIR/../ruff.toml"
		--config "lint.mccabe.max-complexity = $int_max"
		--output-format concise
		--no-cache
	)

	# ⚠️ `|| int_status=$?` on the invocation itself, not a bare call followed by `$?`. Under
	# `set -e` a bare call would be exempt only because a caller three levels up happens to
	# use `report_tree … || int_errors=1`, which suspends errexit for this whole call tree.
	# That is true today and is not a property anyone should have to know: capture the status
	# where it is produced, and the correctness stops depending on a distant caller.
	# ⚠️ THE SUBSHELL IS THE COLOUR FIX, and the vars it unsets are not interchangeable with
	# the one it sets. ruff renders `path:line:col:` with ANSI escapes around every separator
	# when colour is on; those escapes then travel with the digits into `cut -d:` and into an
	# arithmetic expansion, which dies with `[0m101[36m: syntax error: operand expected` — a
	# message naming neither ruff, nor colour, nor this gate. Measured 2026-08-23: 6 of 6
	# tiers red on a clean tree, purely because the developer's shell exported FORCE_COLOR.
	#
	# ⚠️ `NO_COLOR=1` ALONE DOES NOT FIX IT. Measured against ruff 0.11.13: with FORCE_COLOR=3
	# also set, ruff still colours — the forcing variable wins, and TERM=dumb does not change
	# that. So the forcing variables must be UNSET; NO_COLOR is kept only as the standard
	# belt-and-braces for the case where stdout is a terminal.
	#
	# A subshell rather than `env -u …` because the poetry branch calls a shell FUNCTION,
	# which `env` cannot exec — and rather than `local`, which does not hide an exported
	# global from a child process (measured; the child still saw FORCE_COLOR=3). The parent's
	# environment is left untouched, so a caller that wants colour elsewhere still gets it.
	str_stderr="$(mktemp)"
	int_status=0
	(
		unset FORCE_COLOR CLICOLOR_FORCE
		export NO_COLOR=1
		if [[ "$STR_RUFF_MODE" == "poetry" ]]; then
			run_poetry run ruff "${list_args[@]}"
		else
			ruff "${list_args[@]}"
		fi
	) 2>"$str_stderr" || int_status=$?

	# ruff exits 0 (clean) or 1 (violations found) — 1 is DATA here, not failure. Anything
	# else means ruff could not run, and that must never look like a clean tree: re-print
	# what ruff actually said instead of guessing about output we discarded.
	if ((int_status > 1)); then
		print_status "error" "ruff failed on '$str_dir' (exit $int_status):"
		cat "$str_stderr" >&2
		rm -f "$str_stderr"
		exit 1
	fi
	rm -f "$str_stderr"
}

line_has_reasoned_hatch() {
	# True only when the function's SIGNATURE carries the marker AND a non-empty reason.
	#
	# ⚠️ Scans the whole signature, not just the reported line. ruff anchors C901 on the `def`,
	# but `ruff format` re-wraps a long signature and pushes a trailing comment down onto the
	# closing-paren line — so a hatch written correctly on the `def` silently stopped counting
	# the moment the formatter touched the file. Measured on `CreateLog._validate_path`. This
	# repo's own ruff.toml states the general rule: before making a style load-bearing, check
	# whether the FORMATTER already forbids it — the formatter wins, so the gate adapts.
	local str_file="$1" int_line="$2"
	local str_source str_reason int_scan int_last

	# The signature runs from the `def` to the first line ending in a colon.
	int_last=$((int_line + _INT_SIGNATURE_SCAN_LINES))
	for ((int_scan = int_line; int_scan <= int_last; int_scan++)); do
		str_source="$(sed -n "${int_scan}p" "$str_file" 2>/dev/null || true)"
		[[ -n "$str_source" ]] || break

		if [[ "$str_source" == *"$STR_ALLOW_MARKER"* ]]; then
			str_reason="${str_source#*"$STR_ALLOW_MARKER"}"
			# Strip leading whitespace; a bare marker leaves nothing and is rejected.
			str_reason="${str_reason#"${str_reason%%[![:space:]]*}"}"
			[[ -n "$str_reason" ]] && return 0
			return 1
		fi

		# Stop at the end of the signature: the first line whose code half ends in a colon.
		[[ "${str_source%%#*}" =~ :[[:space:]]*$ ]] && break
	done
	return 1
}

report_tree() {
	# Print every unhatched finding for one tree; return 1 when any survived.
	#
	# ⚠️ ruff's output goes to a FILE, then the file is read — deliberately not
	# `while read … < <(run_ruff_c901 …)`. A process substitution runs in a subshell, so a
	# hard failure inside it (ruff unable to run) could only `exit` that subshell: the loop
	# would read nothing, the tree would report clean, and the gate would be blind for the
	# second time in the same file. Running it synchronously keeps the exit status in the
	# shell that has to act on it.
	local str_dir="$1" int_max="$2"
	local str_findings str_finding str_file int_line int_errors=0

	[[ -d "$str_dir" ]] || return 0

	str_findings="$(mktemp)"
	run_ruff_c901 "$str_dir" "$int_max" >"$str_findings"

	while IFS= read -r str_finding; do
		[[ "$str_finding" == *C901* ]] || continue
		str_file="${str_finding%%:*}"
		int_line="$(printf '%s' "$str_finding" | cut -d: -f2)"

		if line_has_reasoned_hatch "$str_file" "$int_line"; then
			continue
		fi
		print_status "error" "$str_finding (max $int_max in $str_dir/)"
		int_errors=1
	done <"$str_findings"

	rm -f "$str_findings"
	return "$int_errors"
}

count_python_files() {
	# Total .py files across the configured trees — the number printed on success.
	local str_dir int_total=0 int_here
	for str_dir in "${!DICT_MAX_COMPLEXITY[@]}"; do
		[[ -d "$str_dir" ]] || continue
		int_here="$(find "$str_dir" -type f -name '*.py' | wc -l)"
		int_total=$((int_total + int_here))
	done
	printf '%s' "$int_total"
}

check_all_trees() {
	# Run every configured tree at its own ceiling; return 1 if any tree reported.
	local str_dir int_errors=0

	for str_dir in "${!DICT_MAX_COMPLEXITY[@]}"; do
		report_tree "$str_dir" "${DICT_MAX_COMPLEXITY[$str_dir]}" || int_errors=1
	done

	return "$int_errors"
}

main() {
	parse_args "$@"
	bootstrap_init >/dev/null 2>&1 || true
	cd "$STR_ROOT" || exit 1

	resolve_ruff
	if [[ -z "$STR_RUFF_MODE" ]]; then
		# ⚠️ NOT a graceful skip. ruff is a declared dev dependency and the project's own
		# linter — its absence is a broken environment, not a constrained box, and a gate
		# that reports its own blindness as OK is the failure mode this repo writes gates
		# to prevent.
		print_status "error" "ruff not resolvable (tried 'poetry run ruff' and PATH)."
		exit 1
	fi

	INT_FILES_SEEN="$(count_python_files)"
	if [[ "$INT_FILES_SEEN" -eq 0 ]]; then
		# A broken glob would otherwise report success forever.
		print_status "error" "No Python files found under ${!DICT_MAX_COMPLEXITY[*]} — refusing to report success."
		exit 1
	fi

	if ! check_all_trees; then
		print_status "error" "Reduce the branching, or annotate the def line: # $STR_ALLOW_MARKER <reason>"
		exit 1
	fi

	print_status "success" "Cyclomatic complexity within limits ($INT_FILES_SEEN Python file(s))."
}

main "$@"

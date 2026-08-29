#!/usr/bin/env bash
#
# lint_deps.sh — deptry over src/: every imported package is a DIRECT dependency.
#
# WHY THIS EXISTS. The rule was already written down ("Every imported package is a direct
# dependency. If a module `import`s a package, declare it in pyproject.toml — even when it is
# already installed transitively") and NOTHING checked it. Its failure mode is the worst kind:
# the break arrives the day an UNRELATED upstream drops or version-caps a package you never
# declared, so the trigger never appears in your own diff.
#
# It was not hypothetical. The first run of this gate found both DDD tiers importing pandas in
# five src/utils modules while declaring it nowhere — it arrived only through `wwdates`, a
# business-day calendar. A calendar library dropping pandas is an ordinary release note, and it
# would have broken every DDD project with an ImportError nobody could have predicted locally.
#
# ⚠️ DEPTRY MUST RUN INSIDE THE PROJECT VENV — this is not a preference, and there is
# deliberately NO system-binary fallback (unlike lint_shell.sh / lint_actions.sh, where the
# tool's answer does not depend on which interpreter invoked it). deptry maps an imported
# MODULE name back to the DISTRIBUTION that provides it using the metadata of the environment
# it is running in. Outside the venv that metadata is absent, and the verdict does not merely
# degrade, it INVERTS: measured on ddd-service-native-db, an outside-venv run reported 9
# findings, every one of them false and two of them mutually contradictory ('python-dotenv'
# declared-but-unused AND 'dotenv' missing), while BOTH genuine defects vanished. A confident
# wrong answer in both directions is worse than no gate, so absence is a hard failure here.
#
# ⚠️ THE CONFIG LIVES IN pyproject.toml, PER TIER — never in a shared deptry.toml, however
# much the one-implementation rule pulls that way. `--config <file>` re-points deptry at that
# file as the MANIFEST as well as the settings, so it stops reading pyproject's dependency
# table: measured, it fell back to requirements.txt (which pins only Poetry itself) and
# relabelled beartype, python-dotenv, wwdates and every DB driver as transitive. The
# dependency list and the settings have to come from the same file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh" # resolve_python / resolve_poetry / run_poetry

# The tree deptry audits: the production package only. bin/ is deliberately OUT of scope —
# it is dev tooling whose imports (yaml, tomli, certifi) belong to the dev group, and a single
# run cannot hold both profiles: every bin/ file would read as production code and turn each
# dev dependency into a DEP004. Auditing bin/ is a separate gate with its own config.
STR_TARGET="src"

count_python_files() {
	# Print the number of .py files under the audited tree. Printed, not global: this one is
	# safe in a subshell because it resolves nothing (contrast resolve_poetry below).
	[[ -d "$STR_TARGET" ]] || return 0
	find "$STR_TARGET" -name '*.py' -type f | wc -l
}

main() {
	cd "$SCRIPT_DIR/.."

	local int_files
	int_files="$(count_python_files)"
	if [[ "$int_files" -eq 0 ]]; then
		# ⚠️ FAIL ON ZERO DISCOVERY. deptry exits 0 when it scans nothing, so a gate whose
		# target directory moved would report success forever — green precisely because it is
		# checking nothing. Assert the count rather than trusting the exit code.
		print_status "error" "No Python files found under $STR_TARGET/ — refusing to report success."
		exit 1
	fi

	# ⚠️ NOT in a subshell. resolve_poetry populates the POETRY_CMD array, and command
	# substitution would leave it unset in the caller — every later run_poetry then fails while
	# the gate reports a clean tree, the exact defect check_complexity.sh carries a comment
	# about (measured there as 79 known violations reported as success).
	PYTHON="$(resolve_python 2>/dev/null)" || true
	export PYTHON
	if ! resolve_poetry >/dev/null 2>&1 || ! run_poetry run deptry --version >/dev/null 2>&1; then
		print_status "error" "deptry not resolvable via 'poetry run' (poetry install --with dev)."
		print_status "error" "There is no PATH fallback on purpose: outside the venv deptry inverts its own verdict — see the header."
		exit 1
	fi

	print_status "info" "deptry: $int_files Python file(s) under $STR_TARGET/"
	run_poetry run deptry "$STR_TARGET"
	print_status "success" "Every imported package is a declared direct dependency."
}

main "$@"

#!/usr/bin/env bash
# actionlint over this repo's workflows AND the workflows shipped inside templates/.
#
# yamllint validates YAML; actionlint validates a WORKFLOW. A workflow can be impeccable YAML
# and still be rejected wholesale by GitHub — which produces NO red check: the PR merely looks
# like it is waiting, so a dead gate and a slow gate are indistinguishable from the outside.
#
# WHY THE TEMPLATES ARE IN SCOPE: the workflows under templates/ are never executed here, so
# nothing in this repo ever exercised them — every defect in them was discovered by whoever
# scaffolded a project, in their CI, with no way to trace it back. The gate's first run found
# 8, including `actions/cache@v3` (a version GitHub no longer runs) in three tiers and a
# `workflow_call` output whose expression could only ever resolve to the empty string.
#
# One known false positive is tolerated by design: a template's `uses: ./.github/workflows/...`
# resolves relative to the GENERATED project, not to this repo, so actionlint cannot find it
# from here. It is excluded by rule below rather than by silencing the whole check.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Match the shell gate the rest of this repo is held to, so a `run:` block cannot pass one
# gate and fail the other. (A comment may not START with that tool's name — it would parse
# as a lint directive.)
export SHELLCHECK_OPTS="--severity=warning --exclude=SC1091"

# A local reusable workflow inside a template resolves against the generated project root,
# which does not exist here. This is the ONLY tolerated class.
IGNORE_PATTERN='could not read reusable workflow file'

discover_workflows() {
	# ⚠️ Group the expression: `-name '*.yaml' -o -name '*.yml' -type f` parses as
	# `(-name '*.yaml') OR (-name '*.yml' AND -type f)`, because `-o` binds looser than the
	# implicit `-a` — so a DIRECTORY named `*.yaml` would enter the list.
	find .github/workflows templates \
		-path '*/.github/workflows/*' \
		\( -name '*.yml' -o -name '*.yaml' \) -type f 2>/dev/null | sort -u
	find .github/workflows \( -name '*.yml' -o -name '*.yaml' \) -type f 2>/dev/null | sort -u
}

main() {
	# Resolve, don't install — same contract as the lint_* wrappers: a constrained box never
	# hard-fails the commit flow. But a graceful skip is PLACEBO in CI (a gate reporting its
	# own blindness as OK), so the workflow sets LINT_ACTIONS_REQUIRED=1 and the skip becomes
	# a failure there.
	local str_actionlint
	if ! str_actionlint="$(command -v actionlint)"; then
		if [ "${LINT_ACTIONS_REQUIRED:-0}" = "1" ]; then
			echo "actionlint is required here but absent — a skipped gate in CI is a gate reporting its own blindness as OK" >&2
			exit 1
		fi
		echo "skip: actionlint not installed (CI runs it with a pinned, SHA-256-verified binary)"
		echo "      to run it locally: https://github.com/rhysd/actionlint"
		exit 0
	fi

	mapfile -t list_workflows < <(discover_workflows | sort -u)

	# ⚠️ Fail on zero matches. actionlint exits 0 with no arguments, so a wrapper whose
	# discovery matched nothing reports success forever — green precisely because it checks
	# nothing. Assert the count instead of trusting the exit code.
	if [ "${#list_workflows[@]}" -eq 0 ]; then
		echo "no workflow files discovered — actionlint would pass vacuously" >&2
		exit 1
	fi

	echo "actionlint: ${#list_workflows[@]} workflow file(s)"

	local str_output
	str_output="$("$str_actionlint" "${list_workflows[@]}" 2>&1)" || true

	# Drop the tolerated class along with its two quoted context lines, then look for any
	# remaining `path:line:col:` finding.
	local str_real
	str_real="$(printf '%s\n' "$str_output" | grep -E '^[^ ].*:[0-9]+:[0-9]+:' | grep -v "$IGNORE_PATTERN" || true)"

	if [ -n "$str_real" ]; then
		echo "actionlint found workflow problems:" >&2
		printf '%s\n' "$str_output" >&2
		exit 1
	fi

	echo "actionlint OK"
}

main "$@"

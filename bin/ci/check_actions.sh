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

# Every job that owns a runner must bound itself. GitHub's default is 6 HOURS, so an
# unbounded job that hangs (a mirror that never answers, a prompt nobody sees) burns a
# full runner-hour budget and then reports `cancelled` — indistinguishable at a glance
# from a human pressing cancel. Measured twice in two days on the same apt-get step
# before this gate existed (#192), across 22 workflows with ZERO bounds between them.
#
# Jobs that only `uses:` a reusable workflow are correctly skipped: GitHub rejects
# timeout-minutes there, and the called workflow carries its own bound.
check_job_timeouts() {
	local str_file str_findings=""
	for str_file in "$@"; do
		str_findings+="$(awk '
			/^  [A-Za-z0-9_-]+:[[:space:]]*$/ {
				if (str_job != "" && int_runs && !int_timeout)
					printf "%s: job \"%s\" has runs-on but no timeout-minutes\n", FILENAME, str_job
				str_job = $0
				sub(/^  /, "", str_job); sub(/:.*$/, "", str_job)
				int_runs = 0; int_timeout = 0
				next
			}
			/^    runs-on:/ { int_runs = 1 }
			/^    timeout-minutes:/ { int_timeout = 1 }
			END {
				if (str_job != "" && int_runs && !int_timeout)
					printf "%s: job \"%s\" has runs-on but no timeout-minutes\n", FILENAME, str_job
			}
		' "$str_file")"
	done

	str_findings="$(printf '%s\n' "$str_findings" | grep -v '^[[:space:]]*$' || true)"
	if [ -n "$str_findings" ]; then
		echo "unbounded workflow jobs (add timeout-minutes):" >&2
		printf '%s\n' "$str_findings" >&2
		exit 1
	fi

	# Print the number, not just "OK": a gate that reports success without saying what it
	# measured is indistinguishable from a gate whose discovery silently emptied out.
	local int_bounded
	int_bounded="$(grep -c '^    timeout-minutes:' "$@" | awk -F: '{ int_sum += $NF } END { print int_sum }')"
	echo "job timeouts OK — ${int_bounded} bounded job(s) across $# workflow(s)"
}

main() {
	mapfile -t list_workflows < <(discover_workflows | sort -u)

	# ⚠️ Fail on zero matches. A wrapper whose discovery matched nothing reports success
	# forever — green precisely because it checks nothing. Assert the count instead of
	# trusting an exit code.
	if [ "${#list_workflows[@]}" -eq 0 ]; then
		echo "no workflow files discovered — the gates below would pass vacuously" >&2
		exit 1
	fi

	# Runs before the actionlint resolve below: this check needs no external tool, so it
	# must not inherit actionlint's graceful skip.
	check_job_timeouts "${list_workflows[@]}"

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

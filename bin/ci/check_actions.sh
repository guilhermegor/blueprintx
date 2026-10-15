#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

export SHELLCHECK_OPTS="--severity=warning --exclude=SC1091"

IGNORE_PATTERN='could not read reusable workflow file'

discover_workflows() {
	find .github/workflows templates \
		\( -path '*/.github/workflows/*' -o -path '*/optional/deploy/*' \) \
		\( -name '*.yml' -o -name '*.yaml' \) -type f 2>/dev/null | sort -u
	find .github/workflows \( -name '*.yml' -o -name '*.yaml' \) -type f 2>/dev/null | sort -u
}

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

	local int_bounded
	int_bounded="$(grep -c '^    timeout-minutes:' "$@" | awk -F: '{ int_sum += $NF } END { print int_sum }')"
	echo "job timeouts OK — ${int_bounded} bounded job(s) across $# workflow(s)"
}

check_action_pins() {
	local str_file str_findings=""
	for str_file in "$@"; do
		str_findings+="$(awk '
			/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*[^.[:space:]]/ {
				str_ref = $0
				sub(/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*/, "", str_ref)
				if (str_ref !~ /^[^@[:space:]]+@[0-9a-f]{40}[[:space:]]+#[[:space:]]*v[0-9]/)
					printf "%s:%d: not pinned to a commit SHA: %s\n", FILENAME, NR, str_ref
			}
		' "$str_file")"$'\n'
	done

	str_findings="$(printf '%s\n' "$str_findings" | grep -v '^[[:space:]]*$' || true)"
	if [ -n "$str_findings" ]; then
		echo "unpinned action references (use <owner>/<repo>@<40-hex sha> # vX.Y.Z):" >&2
		printf '%s\n' "$str_findings" >&2
		exit 1
	fi

	local int_pinned
	int_pinned="$(grep -cE 'uses:[[:space:]]*[^./[:space:]][^@]*@[0-9a-f]{40}' "$@" | awk -F: '{ int_sum += $NF } END { print int_sum }')"
	echo "action pins OK — ${int_pinned} SHA-pinned reference(s) across $# workflow(s)"
}

main() {
	mapfile -t list_workflows < <(discover_workflows | sort -u)

	if [ "${#list_workflows[@]}" -eq 0 ]; then
		echo "no workflow files discovered — the gates below would pass vacuously" >&2
		exit 1
	fi

	check_job_timeouts "${list_workflows[@]}"
	mapfile -t list_template_workflows < <(printf '%s\n' "${list_workflows[@]}" | grep '^templates/' || true)
	if [ "${#list_template_workflows[@]}" -eq 0 ]; then
		echo "no template workflows discovered — the pin gate would pass vacuously" >&2
		exit 1
	fi
	check_action_pins "${list_template_workflows[@]}"

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

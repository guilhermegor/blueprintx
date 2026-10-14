#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

run_worker() {
	local str_tier="$1" path_logdir="$2"
	local path_sandbox int_status int_start

	path_sandbox="$(mktemp -d)"
	# shellcheck disable=SC2064  # expand path_sandbox NOW: the trap must survive this function.
	trap "rm -rf '$path_sandbox'" EXIT

	cp -a "$REPO_ROOT/templates" "$REPO_ROOT/bin" "$path_sandbox/"

	int_start="$SECONDS"
	if PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring" POETRY_NO_INTERACTION=1 \
		bash "$path_sandbox/bin/ci/scaffold_lint_test.sh" "$str_tier" \
		>"$path_logdir/$str_tier.log" 2>&1; then
		int_status=0
	else
		int_status=$?
	fi

	printf '%s %s\n' "$int_status" "$((SECONDS - int_start))" >"$path_logdir/$str_tier.status"

	if [ "$int_status" -eq 0 ]; then
		echo "  PASS  $str_tier  ($((SECONDS - int_start))s)"
	else
		echo "  FAIL  $str_tier  ($((SECONDS - int_start))s, exit $int_status)"
	fi
	return 0
}

if [ "${1:-}" = "--worker" ]; then
	run_worker "$2" "$3"
	exit 0
fi

discover_python_tiers() {
	local path_meta str_language
	for path_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
		[ -f "$path_meta" ] || continue
		str_language="$(grep '^language=' "$path_meta" | cut -d= -f2-)"
		[ "$str_language" = "python" ] || continue
		basename "$(dirname "$path_meta")"
	done | sort
}

main() {
	local int_jobs=0
	if [ "${1:-}" = "--jobs" ]; then
		int_jobs="${2:?--jobs needs a number}"
	fi

	local -a list_tiers
	mapfile -t list_tiers < <(discover_python_tiers)

	if [ "${#list_tiers[@]}" -eq 0 ]; then
		echo "ERROR: no Python tiers found under templates/*/skeleton.meta — refusing to report success." >&2
		exit 1
	fi

	if [ "$int_jobs" -le 0 ]; then
		local int_cpus
		int_cpus="$(nproc 2>/dev/null || echo 2)"
		int_jobs=$((int_cpus < ${#list_tiers[@]} ? int_cpus : ${#list_tiers[@]}))
	fi

	local path_logdir
	path_logdir="$(mktemp -d)"
	# shellcheck disable=SC2064  # expand now, same reason as the worker's trap.
	trap "rm -rf '$path_logdir'" EXIT

	echo "::group::Scaffold + lint + test — ${#list_tiers[@]} Python tier(s), ${int_jobs} at a time"
	printf '%s\n' "${list_tiers[@]}" |
		xargs -P "$int_jobs" -I{} bash "$SCRIPT_DIR/scaffold_lint_test_all.sh" --worker {} "$path_logdir" || true
	echo "::endgroup::"

	local int_failed=0 str_tier int_status int_secs
	for str_tier in "${list_tiers[@]}"; do
		if [ ! -f "$path_logdir/$str_tier.status" ]; then
			echo "ERROR: $str_tier produced no verdict (worker died before reporting)" >&2
			int_failed=$((int_failed + 1))
			continue
		fi
		read -r int_status int_secs <"$path_logdir/$str_tier.status"
		[ "$int_status" -eq 0 ] && continue
		int_failed=$((int_failed + 1))
		echo "::group::FAILED — $str_tier (${int_secs}s, exit $int_status)"
		cat "$path_logdir/$str_tier.log" >&2
		echo "::endgroup::"
	done

	if [ "$int_failed" -ne 0 ]; then
		echo "ERROR: $int_failed of ${#list_tiers[@]} tier(s) failed." >&2
		exit 1
	fi
	echo "OK: all ${#list_tiers[@]} Python tiers scaffold clean, lint clean, and pass their tests."
}

main "$@"

#!/usr/bin/env bash
# scaffold_lint_test_all.sh — run bin/ci/scaffold_lint_test.sh over EVERY Python tier, in parallel.
#
# scaffold_lint_test.sh is the real verification for template work (CLAUDE.md: checking at the
# template root is a false green), so every template change owes a run across all five Python
# tiers. GitHub Actions already fans that out into five jobs; locally there was nothing, so it got
# driven by a hand-written loop that ran the tiers one at a time — ~10 minutes of mostly waiting,
# paid on every iteration.
#
# ⚠️ THE TIERS ARE NOT INDEPENDENT, WHICH IS WHY EACH WORKER GETS ITS OWN SANDBOX.
# "they share no state" is the obvious assumption and it is false. scaffold_lint_test.sh seeds
# cache fixtures before scaffolding (blueprintx#205) and removes them in an EXIT trap — and SIX of
# its eight fixtures live in the SHARED templates/python-common/ tree:
#
#     templates/python-common/src/utils/{__pycache__,.ruff_cache,seeded_probe.pyc,seeded_probe.pyo}
#     templates/python-common/optional/typing/{__pycache__,.mypy_cache}
#
# Run two tiers concurrently against one working tree and the FIRST to finish deletes the fixtures
# the others are still using. The resulting failure is intermittent AND misattributed — a
# cache-leak assertion failing in a tier that did nothing wrong — which is strictly worse than the
# slow loop it replaced. Copying templates/ + bin/ per worker costs ~9 MB (the repo's bulk is
# .venv, not tracked content), so isolation is the cheap answer rather than a clever lock.
#
# Usage:
#   bash bin/ci/scaffold_lint_test_all.sh              # all Python tiers, auto job count
#   bash bin/ci/scaffold_lint_test_all.sh --jobs 2     # cap concurrency
#   bash bin/ci/scaffold_lint_test_all.sh --jobs 1     # sequential — the debugging escape hatch
#
# CI does NOT need this: tests.yaml already runs one job per tier, which is the same fan-out with
# better isolation. This exists for the local loop.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── worker mode ───────────────────────────────────────────────────────────────
# Self-invocation, one tier per process. A separate mode rather than a bash function because
# `xargs -P` can only fan out over a COMMAND, and exporting a function to subshells is the kind
# of cleverness that breaks under a different shell.
run_worker() {
	local str_tier="$1" path_logdir="$2"
	local path_sandbox int_status int_start

	path_sandbox="$(mktemp -d)"
	# shellcheck disable=SC2064  # expand path_sandbox NOW: the trap must survive this function.
	trap "rm -rf '$path_sandbox'" EXIT

	# Only these two trees are read: scaffold_lint_test.sh resolves its own REPO_ROOT from
	# $0, reads templates/<tier>/skeleton.meta, and execs the bin/scaffold/*.sh named there.
	cp -a "$REPO_ROOT/templates" "$REPO_ROOT/bin" "$path_sandbox/"

	# ⚠️ DISABLE THE KEYRING, OR CONCURRENT `poetry install` RACES ON THE DBUS SESSION BUS.
	# Measured on the first parallel run: 1 of 5 tiers died with
	#   "Message recipient disconnected from message bus without replying"
	# inside `poetry install`, while the same five passed sequentially. Poetry probes the system
	# keyring for index credentials; several probes against one session bus is what breaks, so the
	# failure is a function of the JOB COUNT and not of the tier — it lands on whichever worker
	# loses the race, which is exactly the shape that gets misread as a flaky template.
	#
	# Set HERE and not in scaffold_lint_test.sh: that harness also runs as one job per tier in CI,
	# where there is no contention and nothing to fix. The fix belongs to the thing that introduces
	# the concurrency. Nothing here needs credentials — it scaffolds a throwaway project and
	# installs from the public index.
	int_start="$SECONDS"
	if PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring" POETRY_NO_INTERACTION=1 \
		bash "$path_sandbox/bin/ci/scaffold_lint_test.sh" "$str_tier" \
		>"$path_logdir/$str_tier.log" 2>&1; then
		int_status=0
	else
		int_status=$?
	fi

	# The status FILE is the real channel, not the exit code: `xargs -P` collapses every worker's
	# status into one number (123 = "something failed"), which cannot say WHICH tier.
	printf '%s %s\n' "$int_status" "$((SECONDS - int_start))" >"$path_logdir/$str_tier.status"

	if [ "$int_status" -eq 0 ]; then
		echo "  PASS  $str_tier  ($((SECONDS - int_start))s)"
	else
		echo "  FAIL  $str_tier  ($((SECONDS - int_start))s, exit $int_status)"
	fi
	return 0 # never abort the fan-out; the summary decides the verdict
}

if [ "${1:-}" = "--worker" ]; then
	run_worker "$2" "$3"
	exit 0
fi

# ── main ──────────────────────────────────────────────────────────────────────
discover_python_tiers() {
	# A tier is a templates/*/skeleton.meta declaring language=python. Never a hardcoded list:
	# the discovery system exists precisely so adding a skeleton needs no edit here.
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

	# ⚠️ FAIL ON ZERO DISCOVERY. With no tiers, xargs runs nothing and every status check passes
	# vacuously — success for having verified nothing, the exact failure this repo writes gates to
	# prevent (see lint_actions.sh and check_complexity.sh, which each carry this guard).
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

	# Verdict from the status files, never from xargs' collapsed exit code.
	local int_failed=0 str_tier int_status int_secs
	for str_tier in "${list_tiers[@]}"; do
		if [ ! -f "$path_logdir/$str_tier.status" ]; then
			# A worker that never wrote a status did not merely fail — it died before it could
			# report, and treating a missing verdict as a pass is how a harness reports success
			# for a tier it never ran.
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

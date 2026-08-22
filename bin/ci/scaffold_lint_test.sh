#!/usr/bin/env bash
# Real (non-dry-run) scaffold of a Python skeleton, then run the generated
# project's own quality gate end-to-end: `make lint` (and assert it changed
# nothing) followed by `make unit_tests`.
#
# This complements bin/ci/smoke_test.sh, which only does `--dry-run` (prints the
# structure, writes no files). Here we actually generate the project and prove a
# fresh scaffold lints clean and its unit tests pass — so a template defect that
# would otherwise surface only in a downstream project is caught in BlueprintX CI.
#
# Usage:  bash bin/ci/scaffold_lint_test.sh <skeleton>
# Non-Python skeletons are skipped (exit 0).

set -euo pipefail

SKELETON="${1:?skeleton name required}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
META="$REPO_ROOT/templates/$SKELETON/skeleton.meta"

[ -f "$META" ] || { echo "ERROR: skeleton '$SKELETON' not found" >&2; exit 1; }

str_language="$(grep '^language=' "$META" | cut -d= -f2-)"
if [ "$str_language" != "python" ]; then
    echo "Skipping '$SKELETON' — not a Python skeleton (language=$str_language)."
    exit 0
fi

str_scaffold_rel="$(grep '^scaffold=' "$META" | cut -d= -f2-)"
[ -n "$str_scaffold_rel" ] || { echo "ERROR: no scaffold= in $META" >&2; exit 1; }

# Git identity is required for the scaffold's first commit; CI runners have none.
git config --global user.email >/dev/null 2>&1 || git config --global user.email "ci-bot@example.com"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "ci-bot"

WORK_DIR="$(mktemp -d)"
PROJECT_NAME="ci_scaffold"
PROJECT_PATH="$WORK_DIR/$PROJECT_NAME"

# Seed interpreter caches into templates/ BEFORE scaffolding (#205).
#
# `cp -r` has no exclusion mechanism, so a __pycache__ sitting in templates/ is copied
# into the generated project. CI checks out fresh and therefore never has one — which is
# exactly why this shipped unnoticed from maintainers' machines for as long as it did. The
# only way this harness can see the defect is to reproduce the precondition itself.
# ⚠️ ONE ENTRY PER DIRECTORY NAME THE ASSERTION REJECTS. Seeding only __pycache__ while the
# check also rejects .pytest_cache/.ruff_cache/.mypy_cache would leave three quarters of that
# assertion never exercised — a check that cannot fail for the cases it claims to cover, which
# is the same vacuous shape the seeding exists to close. Raised by review on #215.
SEEDED_CACHES=(
    "$REPO_ROOT/templates/$SKELETON/src/__pycache__"
    "$REPO_ROOT/templates/$SKELETON/src/.pytest_cache"
    "$REPO_ROOT/templates/python-common/src/utils/__pycache__"
    "$REPO_ROOT/templates/python-common/src/utils/.ruff_cache"
    "$REPO_ROOT/templates/python-common/optional/typing/__pycache__"
    "$REPO_ROOT/templates/python-common/optional/typing/.mypy_cache"
)
# Loose compiled artifacts, which live OUTSIDE a cache directory and are pruned by the second
# `find` in scaffold_purge_caches — the half the directory fixtures above cannot reach.
SEEDED_FILES=(
    "$REPO_ROOT/templates/python-common/src/utils/seeded_probe.pyc"
    "$REPO_ROOT/templates/python-common/src/utils/seeded_probe.pyo"
)
cleanup() {
    rm -rf "$WORK_DIR" "${SEEDED_CACHES[@]}" "${SEEDED_FILES[@]}"
}
trap cleanup EXIT

int_seeded=0
for str_cache in "${SEEDED_CACHES[@]}"; do
    # Only seed under a directory the template already has — creating the parent would
    # change what the scaffold copies, which is not what this test is for.
    [ -d "$(dirname "$str_cache")" ] || continue
    mkdir -p "$str_cache"
    printf 'seeded by scaffold_lint_test.sh\n' >"$str_cache/seeded.cpython-000.pyc"
    int_seeded=$((int_seeded + 1))
done
for str_file in "${SEEDED_FILES[@]}"; do
    [ -d "$(dirname "$str_file")" ] || continue
    printf 'seeded by scaffold_lint_test.sh\n' >"$str_file"
    int_seeded=$((int_seeded + 1))
done
# Every rejected directory name must have been seeded at least once, or that branch of the
# assertion is untested. lib-minimal has no templates/lib-minimal/src, hence the -ge 4 floor
# (the four python-common fixtures) rather than a count of the whole list.
[ "$int_seeded" -ge 4 ] || {
    echo "ERROR: seeded $int_seeded fixture(s) — too few for the purge check to mean anything" >&2
    exit 1
}

echo "::group::Scaffold $SKELETON (offline, no opt-ins)"
# Feed a generous run of "n" answers: declines docker / storage / data-dir /
# webhook / remote across every tier (extra lines are harmless). With no remote,
# the scaffold lands in offline mode (local git workflow + protect-branch).
# A finite printf (not `yes`) avoids SIGPIPE once the scaffold stops reading.
printf 'n\n%.0s' {1..12} | GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold_rel" \
    "$WORK_DIR" "$PROJECT_NAME" "CI scaffold lint+test" "0.0.1"
echo "::endgroup::"

# The generated project's own .gitignore lists __pycache__/, so a copied cache is invisible
# to `git status` downstream — `find` is the only witness (#205).
str_leaked="$(find "$PROJECT_PATH" \
    \( -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \
    -o -name '.mypy_cache' \) -o -type f -name '*.py[cod]' \) -print)"
if [ -n "$str_leaked" ]; then
    echo "ERROR: the scaffold shipped interpreter/tool caches into the generated project:" >&2
    echo "$str_leaked" >&2
    exit 1
fi
echo "No interpreter/tool caches leaked into the generated project."

# This harness scaffolds OFFLINE (it declines the remote), so the GitHub-only assets must be
# absent. Asserting it here is what stops a workflow being shipped into a project that has no
# Actions to run it: dead weight that can never go green, and nothing else would notice.
for str_online_only in coderabbit_trigger.yaml review_threads.yaml; do
    if [ -e "$PROJECT_PATH/.github/workflows/$str_online_only" ]; then
        echo "ERROR: offline scaffold shipped the GitHub-only $str_online_only" >&2
        exit 1
    fi
done
echo "No GitHub-only workflows in the offline project."

cd "$PROJECT_PATH"

echo "::group::poetry install (runtime + dev)"
# In-project venv (poetry.toml). Drivers/runtime ship as wheels — no system libs
# needed to install, and the unit tests import DB drivers lazily (never at import
# time), so the env is sufficient for both lint and unit tests.
poetry install --with dev --no-interaction --no-ansi
echo "::endgroup::"

# Commit anything left in the tree as the baseline, AFTER poetry install (the
# scaffold already commits its own output, including offline artifacts; this
# mainly captures the generated poetry.lock). With a clean baseline, the
# post-lint check below reflects only what `make lint` itself changes.
git add -A
git commit -q --no-verify -m "ci: scaffold baseline" || true

echo "::group::make lint (must leave the tree unchanged)"
make lint
# `make lint` auto-fixes (ruff --fix / format). On a clean scaffold it must change
# nothing — any diff or new file means the template shipped non-compliant code.
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: 'make lint' modified the freshly scaffolded tree:" >&2
    git status --short >&2
    git --no-pager diff >&2
    exit 1
fi
echo "make lint left the tree clean."
echo "::endgroup::"

echo "::group::make unit_tests"
make unit_tests
echo "::endgroup::"

# The integration suite is where every bin/*.sh seam is actually EXECUTED — the unit suite
# cannot reach a shell script. Without this step those tests were written, shipped into every
# tier, and never run by the one harness that proves a tier works, so a broken shell seam
# looked exactly like a working one. `|| [ $? -eq 5 ]` tolerates pytest's "no tests collected"
# for a tier that ships none; a real failure (exit 1) still fails the run.
echo "::group::make integration_tests"
make integration_tests || [ $? -eq 5 ]
echo "::endgroup::"

echo "OK: $SKELETON scaffolds clean, lints clean, and unit + integration tests pass."

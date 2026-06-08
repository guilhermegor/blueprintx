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
trap 'rm -rf "$WORK_DIR"' EXIT
PROJECT_NAME="ci_scaffold"
PROJECT_PATH="$WORK_DIR/$PROJECT_NAME"

echo "::group::Scaffold $SKELETON (offline, no opt-ins)"
# Feed a generous run of "n" answers: declines docker / storage / data-dir /
# webhook / remote across every tier (extra lines are harmless). With no remote,
# the scaffold lands in offline mode (local git workflow + protect-branch).
# A finite printf (not `yes`) avoids SIGPIPE once the scaffold stops reading.
printf 'n\n%.0s' {1..12} | GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold_rel" \
    "$WORK_DIR" "$PROJECT_NAME" "CI scaffold lint+test" "0.0.1"
echo "::endgroup::"

cd "$PROJECT_PATH"

echo "::group::poetry install (runtime + dev)"
# In-project venv (poetry.toml). Drivers/runtime ship as wheels — no system libs
# needed to install, and the unit tests import DB drivers lazily (never at import
# time), so the env is sufficient for both lint and unit tests.
poetry install --with dev --no-interaction --no-ansi
echo "::endgroup::"

# Commit the full tree as the baseline, AFTER poetry install (so the generated
# poetry.lock is captured too). The scaffold makes its first commit before
# switching to offline mode, so the offline artifacts (local git workflow,
# swapped pre-commit hook, removed .github) are otherwise left uncommitted. With
# everything committed, the post-lint check below reflects only what `make lint`
# changes.
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

echo "OK: $SKELETON scaffolds clean, lints clean, and unit tests pass."

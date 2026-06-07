#!/usr/bin/env bash
# Builds the MkDocs site in --strict mode so broken refs/nav fail the check.
# Single source of truth shared by the Scaffold Checks CI (docs-build job) and
# the root pre-commit hook. Prefers `poetry run` when a venv is available
# (local dev) and falls back to a bare `mkdocs` on the PATH (CI installs it
# globally via pip).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if command -v poetry >/dev/null 2>&1 && poetry run mkdocs --version >/dev/null 2>&1; then
	poetry run mkdocs build --strict
else
	mkdocs build --strict
fi

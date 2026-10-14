#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if command -v poetry >/dev/null 2>&1 && poetry run mkdocs --version >/dev/null 2>&1; then
	poetry run mkdocs build --strict
else
	mkdocs build --strict
fi

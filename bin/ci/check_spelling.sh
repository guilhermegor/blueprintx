#!/usr/bin/env bash
# Spell-checks docs/ and templates/ with codespell, using the root .codespellrc
# for the curated ignore list. This is the single source of truth shared by the
# Scaffold Checks CI (spell-check job) and the root pre-commit hook — neither
# inlines the flags, so the two cannot drift.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

codespell docs/ templates/ --config=.codespellrc

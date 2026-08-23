#!/usr/bin/env bash
#
# test_cov.sh — unit tests with coverage, plus the badge the README renders.
#
# Four steps that only make sense as a sequence: pytest writes .coverage, `coverage report`
# prints it for a human, `coverage xml` serialises it, and genbadge turns that XML into
# coverage.svg. Splitting them across a recipe in two files (Makefile + tasks.sh) meant the
# ORDER lived in two places; it lives here now.
#
# ⚠️ genbadge runs with --local deliberately: it renders the badge offline instead of
# fetching shields.io. A build step that reaches the network fails behind a corporate proxy
# and in an air-gapped CI runner, and a badge is not worth either.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

cd "$SCRIPT_DIR/.."

POETRY="bash $SCRIPT_DIR/poetry_exec.sh"

print_status info "pytest tests/unit/ --cov=src"
$POETRY run pytest tests/unit/ --cov=src

print_status info "coverage report"
$POETRY run coverage report -m

print_status info "coverage xml"
$POETRY run coverage xml -o coverage.xml

print_status info "coverage badge"
$POETRY run genbadge coverage --local -i coverage.xml -o coverage.svg

print_status success "coverage report and badge written"

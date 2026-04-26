#!/usr/bin/env bash
# run.sh — Bash alternative to Makefile (no make required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------
# VIRTUAL ENVIRONMENT
# -------------------

venv() {
    PY_VERSION=$(cat "$SCRIPT_DIR/.python-version" 2>/dev/null || echo "3.11.12")
    pyenv install "$PY_VERSION" -s
    pyenv local "$PY_VERSION"
    python -m pip install --upgrade pip
    python -m pip install -r "$SCRIPT_DIR/requirements.txt"
    poetry config virtualenvs.in-project true --local
    poetry install
    echo "Virtual environment created in ./.venv"
    echo "Poetry project installed"
    poetry run playwright install
    echo "Playwright installed"
}

update_venv() {
    poetry update
    echo "Poetry project updated"
}

precommit() {
    poetry run pre-commit install
    poetry run pre-commit install --hook-type commit-msg
}

init() {
    venv
    precommit
}

# -------------------
# TESTING
# -------------------

unit_tests() {
    poetry run pytest tests/unit/
}

integration_tests() {
    poetry run pytest tests/integration/
}

test_cov() {
    poetry run pytest tests/unit/ --cov=src
    poetry run coverage report -m
    poetry run coverage-badge -o coverage.svg -f
}

test_slowest() {
    echo "Running tests to identify the 20 slowest tests..."
    poetry run pytest tests/unit/ --durations=20 --tb=short
}

test_feat() {
    if [[ -z "${FEAT:-}" ]]; then
        echo "Usage: FEAT=<keyword> ./run.sh test_feat"
        exit 1
    fi
    poetry run pytest tests/unit/ -k "$FEAT"
}

test_urls_docstrings() {
    bash "$SCRIPT_DIR/bin/test_urls_docstrings.sh"
}

fix_playwright() {
    bash "$SCRIPT_DIR/bin/fix_playwright.sh"
}

# -------------------
# LINTING
# -------------------

lint() {
    poetry run ruff check --fix .
    poetry run ruff format .
    poetry run codespell .
    poetry run pydocstyle .
}

# -------------------
# RUN
# -------------------

start() {
    bash "$SCRIPT_DIR/bin/start.sh"
}

# -------------------
# DOCS
# -------------------

docs_server() {
    pip install --quiet mkdocs-material
    mkdocs serve -a 0.0.0.0:8000 --livereload
}

# -------------------
# HELP
# -------------------

show_help() {
    cat <<EOF

Usage: ./run.sh <command>

Virtual Environment
  init                 Bootstrap venv + install pre-commit hooks
  venv                 Create Poetry venv and install Playwright
  update-venv          Update all Poetry dependencies
  precommit            Install pre-commit hooks (push + commit-msg)

Testing
  unit_tests           Run unit tests with pytest
  integration_tests    Run integration tests with pytest
  test_cov             Run unit tests with coverage report and badge
  test_slowest         Report the 20 slowest unit tests
  FEAT=<kw> test_feat  Run unit tests matching keyword <kw>
  test_urls_docstrings Check all URLs inside docstrings
  fix_playwright       Reinstall Playwright browsers

Linting
  lint                 Run ruff, codespell, pydocstyle

Docs
  docs-server          Serve MkDocs site locally at http://0.0.0.0:8000

Run
  start                Run src/main.py (auto-installs Poetry if missing)

EOF
}

# -------------------
# MAIN
# -------------------

case "${1:-help}" in
    init)                init ;;
    venv)                venv ;;
    update-venv)         update_venv ;;
    precommit)           precommit ;;
    unit_tests)          unit_tests ;;
    integration_tests)   integration_tests ;;
    test_cov)            test_cov ;;
    test_slowest)        test_slowest ;;
    test_feat)           test_feat ;;
    test_urls_docstrings) test_urls_docstrings ;;
    fix_playwright)      fix_playwright ;;
    lint)                lint ;;
    docs-server)         docs_server ;;
    start)               start ;;
    help|--help|-h)      show_help ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

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
# VSCODE CONFIG
# -------------------

vscode_init() {
    bash "$SCRIPT_DIR/scripts/vscode_keybindings.sh"
    bash "$SCRIPT_DIR/scripts/vscode_extensions.sh"
}

export_deps() {
    bash "$SCRIPT_DIR/scripts/export_deps.sh"
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
    local feat="${2:-}"
    if [[ -z "$feat" ]]; then
        echo "Usage: ./run.sh test-feat <keyword>"
        exit 1
    fi
    poetry run pytest tests/unit/ -k "$feat"
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

VS Code
  vscode-init          Install VS Code extensions and keybindings
  export-deps          Export Poetry deps to requirements.txt

Testing
  unit-tests           Run unit tests with pytest
  integration-tests    Run integration tests with pytest
  test-cov             Run unit tests with coverage report and badge
  test-slowest         Report the 20 slowest unit tests
  test-feat <keyword>  Run unit tests matching keyword
  test-urls            Check all URLs inside docstrings
  fix-playwright       Reinstall Playwright browsers

Linting
  lint                 Run ruff, codespell, pydocstyle

  help                 Show this help message

EOF
}

# -------------------
# MAIN
# -------------------

case "${1:-help}" in
    init)              init ;;
    venv)              venv ;;
    update-venv)       update_venv ;;
    precommit)         precommit ;;
    vscode-init)       vscode_init ;;
    export-deps)       export_deps ;;
    unit-tests)        unit_tests ;;
    integration-tests) integration_tests ;;
    test-cov)          test_cov ;;
    test-slowest)      test_slowest ;;
    test-feat)         test_feat "$@" ;;
    test-urls)         test_urls_docstrings ;;
    fix-playwright)    fix_playwright ;;
    lint)              lint ;;
    help|--help|-h)    show_help ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

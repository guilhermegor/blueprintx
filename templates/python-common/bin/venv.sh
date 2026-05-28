#!/usr/bin/env bash
# Set up the Python virtual environment: pyenv-preferred with a system-Python
# fallback (for hosts where pyenv cannot be installed), optional corporate-CA
# wiring, then a Poetry install. Cross-platform logic lives in lib/bootstrap.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

install_deps() {
	print_status "info" "Upgrading pip..."
	"$PYTHON" -m pip install --upgrade pip

	print_status "info" "Configuring Poetry virtualenv (in-project)..."
	run_poetry config virtualenvs.in-project true --local

	print_status "info" "Installing project dependencies..."
	run_poetry install --with dev,docs
	print_status "success" "Dependencies installed"
}

install_playwright() {
	if run_poetry run python -c "import playwright" 2>/dev/null; then
		print_status "info" "Installing Playwright browsers..."
		run_poetry run playwright install chromium --with-deps
		print_status "success" "Playwright installed"
	fi
}

main() {
	print_status "section" "Virtual Environment Setup"
	bootstrap_init
	ensure_python_version
	wire_corporate_ca
	ensure_poetry
	install_deps
	install_playwright
	print_status "success" "Virtual environment ready in ./.venv"
}

main "$@"

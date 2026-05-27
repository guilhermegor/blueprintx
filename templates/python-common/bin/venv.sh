#!/usr/bin/env bash
# Set up the Python virtual environment via pyenv + Poetry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

setup_python() {
	local str_py_version
	str_py_version=$(cat "$SCRIPT_DIR/../.python-version" 2>/dev/null || echo "3.12.2")
	print_status "config" "Python version: $str_py_version"
	pyenv install "$str_py_version" -s
	pyenv local "$str_py_version"
	print_status "success" "Python $str_py_version active"
}

install_deps() {
	print_status "info" "Upgrading pip..."
	python -m pip install --upgrade pip

	if [[ -f "$SCRIPT_DIR/../requirements.txt" ]]; then
		print_status "info" "Installing bootstrap requirements..."
		python -m pip install -r "$SCRIPT_DIR/../requirements.txt"
	fi

	print_status "info" "Configuring Poetry virtualenv (in-project)..."
	poetry config virtualenvs.in-project true --local

	print_status "info" "Installing project dependencies..."
	poetry install --with dev,docs
	print_status "success" "Dependencies installed"
}

install_playwright() {
	if poetry run python -c "import playwright" 2>/dev/null; then
		print_status "info" "Installing Playwright browsers..."
		poetry run playwright install chromium --with-deps
		print_status "success" "Playwright installed"
	fi
}

main() {
	print_status "section" "Virtual Environment Setup"
	setup_python
	install_deps
	install_playwright
	print_status "success" "Virtual environment ready in ./.venv"
}

main "$@"

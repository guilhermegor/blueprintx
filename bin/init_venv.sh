#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

read_py_version() {
	if [[ -f "$ROOT_DIR/.python-version" ]]; then
		cat "$ROOT_DIR/.python-version"
	else
		echo "3.12.0"
	fi
}

main() {
	cd "$ROOT_DIR"

	local py_version
	py_version=$(read_py_version)
	if [[ -z "$py_version" ]]; then
		echo "PY_VERSION is empty; set .python-version" >&2
		exit 1
	fi

	if command -v pyenv >/dev/null 2>&1; then
		if ! pyenv versions --bare | grep -Fx "$py_version" >/dev/null 2>&1; then
			pyenv install "$py_version"
		fi
		pyenv local "$py_version"
	else
		echo "pyenv not found; using current Python"
	fi

	python -m pip install --upgrade pip
	if [[ -f "$ROOT_DIR/requirements.txt" ]]; then
		python -m pip install -r "$ROOT_DIR/requirements.txt"
	fi
	poetry config virtualenvs.in-project true --local
	poetry install
	echo "Virtual environment created in ./.venv"
	echo "Poetry project installed"
}

main "$@"

#!/usr/bin/env bash
# Run src/main.py via Poetry, installing Poetry if absent, falling back to direct Python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

find_python() {
	command -v python3 2>/dev/null || \
	command -v python  2>/dev/null || \
	command -v py      2>/dev/null || \
	true
}

main() {
	local str_py
	str_py=$(find_python)

	if [[ -z "$str_py" ]]; then
		print_status "error" "No Python interpreter found (tried python3, python, py)"
		exit 1
	fi

	export PYTHONPATH=".:src"

	if command -v poetry >/dev/null 2>&1; then
		poetry run python -m src.main
		return $?
	fi

	print_status "warning" "Poetry not found — installing via $str_py -m pip ..."
	if "$str_py" -m pip install "poetry>=2.2.1"; then
		if command -v poetry >/dev/null 2>&1; then
			poetry run python -m src.main
		else
			print_status "warning" "Poetry installed but not in PATH — running directly"
			"$str_py" -m src.main
		fi
	else
		print_status "warning" "pip install failed — falling back to direct execution"
		"$str_py" -m src.main
	fi
}

main "$@"

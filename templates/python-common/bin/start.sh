#!/usr/bin/env bash
# Run src/main.py via Poetry, installing Poetry if absent, falling back to direct Python.

set -euo pipefail

find_python() {
    command -v python3 2>/dev/null || \
    command -v python  2>/dev/null || \
    command -v py      2>/dev/null || \
    true
}

str_py=$(find_python)

if [[ -z "$str_py" ]]; then
    echo "Error: no Python interpreter found (tried python3, python, py)" >&2
    exit 1
fi

if command -v poetry >/dev/null 2>&1; then
    poetry run python src/main.py
    exit $?
fi

echo "Poetry not found — installing via $str_py -m pip ..."
if "$str_py" -m pip install "poetry>=2.2.1"; then
    if command -v poetry >/dev/null 2>&1; then
        poetry run python src/main.py
    else
        echo "Poetry installed but not in PATH — running directly"
        "$str_py" src/main.py
    fi
else
    echo "pip install failed — falling back to direct execution"
    "$str_py" src/main.py
fi

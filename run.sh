#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: ./run.sh <target>

Targets:
  init     Run the interactive BlueprintX scaffolder
  preview  Show available skeletons and examples
  dev      Scaffold into a temporary directory
  dev-clean Scaffold into a temp directory and delete it on exit
  dry-run  Show structure only, no files created
  init_venv   Create a local Poetry venv using .python-version
  update_venv Update dependencies with Poetry
  mkdocs-serve Serve docs locally
  mkdocs-build Build static docs site
  help     Show this help message
EOF
}

read_py_version() {
    if [[ -f "$SCRIPT_DIR/.python-version" ]]; then
        cat "$SCRIPT_DIR/.python-version"
    else
        echo "3.12.0"
    fi
}

init_venv() {
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
    if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
        python -m pip install -r "$SCRIPT_DIR/requirements.txt"
    fi
    poetry config virtualenvs.in-project true --local
    poetry install
    echo "Virtual environment created in ./.venv"
    echo "Poetry project installed"
}

update_venv() {
    poetry update
    echo "Poetry project updated"
}

main() {
    local target="${1:-help}"

    case "$target" in
        init)
            bash "$SCRIPT_DIR/scripts/BlueprintX.sh"
            ;;
        preview)
            bash "$SCRIPT_DIR/scripts/preview.sh"
            ;;
        dev)
            bash "$SCRIPT_DIR/scripts/BlueprintX.sh" --dev
            ;;
        dev-clean)
            bash "$SCRIPT_DIR/scripts/BlueprintX.sh" --dev --clean
            ;;
        dry-run)
            bash "$SCRIPT_DIR/scripts/BlueprintX.sh" --dry-run
            ;;
        init_venv)
            init_venv
            ;;
        update_venv)
            update_venv
            ;;
        mkdocs-serve)
            poetry run mkdocs serve -a 0.0.0.0:8000
            ;;
        mkdocs-build)
            poetry run mkdocs build
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            echo "Unknown target: $target" >&2
            usage >&2
            exit 1
            ;;
    esac
}

main "$@"

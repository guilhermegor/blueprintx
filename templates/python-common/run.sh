#!/usr/bin/env bash
# run.sh — Bash alternative to Makefile (no make required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------
# VIRTUAL ENVIRONMENT
# -------------------

init_venv() {
    bash "$SCRIPT_DIR/scripts/init_venv.sh"
}

update_venv() {
    poetry update
    echo "Poetry project updated"
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
# HELP
# -------------------

show_help() {
    cat <<EOF
Usage: ./run.sh <command>

Commands:
  init-venv      Initialize Python virtual environment (pyenv + poetry)
  update-venv    Update poetry dependencies
  vscode-init    Set up VS Code keybindings and extensions
  export-deps    Export dependencies to requirements.txt
  help           Show this help message

EOF
}

# -------------------
# MAIN
# -------------------

case "${1:-help}" in
    init-venv)
        init_venv
        ;;
    update-venv)
        update_venv
        ;;
    vscode-init)
        vscode_init
        ;;
    export-deps)
        export_deps
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

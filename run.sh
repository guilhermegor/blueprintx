#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: ./run.sh <target>

Targets:
  init     Run the interactive blueprintx scaffolder
  preview  Show available skeletons and examples
  help     Show this help message
EOF
}

main() {
    local target="${1:-help}"

    case "$target" in
        init)
            bash "$SCRIPT_DIR/scripts/blueprintx.sh"
            ;;
        preview)
            bash "$SCRIPT_DIR/scripts/preview.sh"
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

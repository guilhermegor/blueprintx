#!/usr/bin/env bash
set -e

CLI_VERSION="0.0.0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

print_usage() {
    echo "Usage: ${PROJECT_NAME} [options] <command>"
    echo
    echo "Options:"
    echo "  -V, --version  Print version and exit"
    echo "  -h, --help     Show this help"
}

print_version() {
    local str_version
    if str_version=$(git -C "$PROJECT_ROOT" describe --tags --always 2>/dev/null) &&
        [ -n "$str_version" ]; then
        echo "${PROJECT_NAME} ${str_version#v}"
    else
        echo "${PROJECT_NAME} $CLI_VERSION"
    fi
}

main() {
    case "${1:-}" in
        -V | --version)
            print_version
            ;;
        -h | --help | "")
            print_usage
            ;;
        *)
            print_status "error" "Unknown command: $1"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"

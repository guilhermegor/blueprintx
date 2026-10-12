#!/usr/bin/env bash
# ${PROJECT_NAME} entrypoint.
set -e

# Fallback version for installs WITHOUT a .git tree ('make install' stamps the real
# value here at install time). A git checkout ignores this and derives the version
# from the tag via `git describe` — see print_version. Do not hand-bump: the release
# tag is the single source of truth. Mirrors BlueprintX's own bin/blueprintx.sh.
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
    # Prefer the git tag (the single source of truth) when run from a checkout; fall
    # back to the stamped CLI_VERSION literal for a packaged / `make install`ed copy
    # without a .git tree.
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

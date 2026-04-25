#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_status() {
    local status="$1"
    local message="$2"
    case "$status" in
        "success") echo -e "${GREEN}[✓]${NC} ${message}" ;;
        "error") echo -e "${RED}[✗]${NC} ${message}" >&2 ;;
        "warning") echo -e "${YELLOW}[!]${NC} ${message}" ;;
        "info") echo -e "${BLUE}[i]${NC} ${message}" ;;
        "config") echo -e "${CYAN}[→]${NC} ${message}" ;;
        "debug") echo -e "${MAGENTA}[»]${NC} ${message}" ;;
        *) echo -e "[ ] ${message}" ;;
    esac
}

check_unix_filenames() {
    local has_errors=0

    for f in "$@"; do
        if [[ -d "$f" ]] || [[ "$f" == .git/* ]]; then
            continue
        fi

        local filename
        filename=$(basename "$f")

        if [[ "$filename" == *[^a-zA-Z0-9._-]* ]]; then
            print_status "error" "Invalid filename '$filename' in path: $f"
            print_status "error" "Only alphanumeric, ., - and _ are allowed in filenames"
            has_errors=1
        fi
    done

    if [[ $has_errors -eq 0 ]]; then
        print_status "success" "All filenames are valid"
        return 0
    fi
    return 1
}

main() {
    check_unix_filenames "$@" || exit 1
}

main "$@"

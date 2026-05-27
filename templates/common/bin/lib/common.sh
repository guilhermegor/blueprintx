#!/bin/bash
#
# lib/common.sh
#
# Shared shell utilities for scaffolded BlueprintX projects. Sourced by sibling
# scripts so each one shares a single print_status implementation and color set.
#
# Sourcing contract:
#   - Idempotent (guarded with _BX_COMMON_LOADED so re-sourcing is a no-op).
#   - Optional: scripts may set LOG_FILE before sourcing; print_status will tee
#     timestamped output there. If LOG_FILE is unset, console output only.
#   - Refuses direct execution.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/common.sh is meant to be sourced, not executed." >&2
    exit 1
fi

# Re-sourcing guard
if [ -n "${_BX_COMMON_LOADED:-}" ]; then
    return 0
fi
_BX_COMMON_LOADED=1

# ============================================================================
# COLOR VARIABLES
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# ============================================================================
# print_status — standard status-keyword API
# ============================================================================
#
# Usage:
#   print_status <level> <message>
#
# Levels: success | error | warning | info | config | debug | section
# Unknown levels fall through to a neutral "[ ] message" prefix.
# Errors go to stderr; everything else to stdout.
# If $LOG_FILE is set, every call appends a timestamped line to it.

print_status() {
    local status="$1"
    local message="$2"

    case "$status" in
        success)
            echo -e "${GREEN}[✓]${NC} ${message}"
            ;;
        error)
            echo -e "${RED}[✗]${NC} ${message}" >&2
            ;;
        warning)
            echo -e "${YELLOW}[!]${NC} ${message}"
            ;;
        info)
            echo -e "${BLUE}[i]${NC} ${message}"
            ;;
        config)
            echo -e "${CYAN}[→]${NC} ${message}"
            ;;
        debug)
            echo -e "${MAGENTA}[»]${NC} ${message}"
            ;;
        section)
            echo -e "\n${MAGENTA}========================================${NC}"
            echo -e "${MAGENTA} $message${NC}"
            echo -e "${MAGENTA}========================================${NC}\n"
            ;;
        *)
            echo -e "[ ] ${message}"
            ;;
    esac

    if [ -n "${LOG_FILE:-}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$status] $message" >> "$LOG_FILE"
    fi
}

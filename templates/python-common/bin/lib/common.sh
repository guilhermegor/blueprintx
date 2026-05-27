#!/bin/bash
# Sourced lib — not intended to be executed directly.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "bin/lib/common.sh is meant to be sourced, not executed." >&2
    exit 1
fi

# Idempotency guard — safe to source multiple times.
[ "${_BX_COMMON_LOADED:-}" = "1" ] && return 0
_BX_COMMON_LOADED=1

# ── Colour variables ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── print_status <level> <message> ───────────────────────────────────────────
# Levels: success | error | warning | info | config | debug | section
print_status() {
    local str_level="$1"
    local str_message="$2"

    case "$str_level" in
        success) printf "${GREEN}✔ %s${NC}\n"  "$str_message" ;;
        error)   printf "${RED}✘ %s${NC}\n"    "$str_message" >&2 ;;
        warning) printf "${YELLOW}⚠ %s${NC}\n" "$str_message" ;;
        info)    printf "${BLUE}ℹ %s${NC}\n"   "$str_message" ;;
        config)  printf "${CYAN}⚙ %s${NC}\n"   "$str_message" ;;
        debug)   printf "  [debug] %s\n"        "$str_message" ;;
        section)
            printf "\n${CYAN}══════════════════════════════════════════════════════\n"
            printf "  %s\n" "$str_message"
            printf "══════════════════════════════════════════════════════${NC}\n\n"
            ;;
        *)       printf "%s\n" "$str_message" ;;
    esac
}

# ── _read_env_var <KEY> ───────────────────────────────────────────────────────
# Reads a value from .env in the current directory, bypassing Make's $ expansion.
_read_env_var() {
    grep -m1 "^${1}=" .env 2>/dev/null | cut -d'=' -f2- | tr -d "'\""
}

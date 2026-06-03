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

# ── resolve_default_branch [override] ─────────────────────────────────────────
# Echo the repo's default branch (handles main *or* master). Resolution order:
#   1) the [override] argument, else the DEFAULT_BRANCH env var
#   2) origin/HEAD (the remote's default), basename only
#   3) whichever of main / master exists locally
#   4) "main" as a last resort
# Plain-data output (stdout) — the caller captures it; not a status message.
# Shared by new_branch.sh and git_merge_to_main.sh.
resolve_default_branch() {
    local str_override="${1:-${DEFAULT_BRANCH:-}}"
    local str_ref
    local str_candidate

    if [[ -n "$str_override" ]]; then
        printf '%s\n' "$str_override"
        return 0
    fi

    str_ref="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null || true)"
    if [[ -n "$str_ref" ]]; then
        printf '%s\n' "${str_ref##*/}"
        return 0
    fi

    for str_candidate in main master; do
        if git show-ref --verify --quiet "refs/heads/$str_candidate"; then
            printf '%s\n' "$str_candidate"
            return 0
        fi
    done

    printf '%s\n' "main"
}

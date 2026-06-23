#!/bin/bash
#
# lib/common.sh
#
# Shared shell utilities for the BlueprintX repo tooling. Sourced by sibling
# scripts (bin/*.sh, bin/scaffold/*.sh) so each one shares a single
# print_status implementation and color set.
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

# ============================================================================
# print_section — banner separating major phases
# ============================================================================
#
# Usage:
#   print_section <title>
#
# Thin wrapper over the "section" print_status level for call-site readability.

print_section() {
    local title="$1"
    print_status "section" "$title"
}

# ============================================================================
# exit_error — print an error and exit
# ============================================================================
#
# Usage:
#   exit_error <message> [exit_code]
#
# Routes the message through print_status "error" (stderr + log) then exits
# with the given code (default 1).

exit_error() {
    local message="$1"
    local code="${2:-1}"
    print_status "error" "$message"
    exit "$code"
}

# ============================================================================
# resolve_default_branch — find the repo's default branch
# ============================================================================
#
# Usage:
#   target="$(resolve_default_branch [explicit_name])"
#
# Resolution order: explicit argument, then $DEFAULT_BRANCH, then the remote's
# origin/HEAD, then a local "main", else "master". Used by the git-workflow
# targets (new_branch / git_merge_to_main) so both agree on the integration
# branch.

resolve_default_branch() {
    local explicit="${1:-}"
    if [ -n "$explicit" ]; then
        echo "$explicit"
        return 0
    fi
    if [ -n "${DEFAULT_BRANCH:-}" ]; then
        echo "$DEFAULT_BRANCH"
        return 0
    fi

    local head_ref
    head_ref="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
    if [ -n "$head_ref" ]; then
        echo "${head_ref#origin/}"
        return 0
    fi

    if git show-ref --verify --quiet refs/heads/main; then
        echo "main"
        return 0
    fi
    echo "master"
}

# ============================================================================
# Env-wise config prompt + apply (shared by every Python service scaffold)
# ============================================================================
#
# A project's config can ship as a single inputs.yaml/outputs.yaml (default) or
# as env-suffixed pairs (inputs_dev.yaml/inputs_prd.yaml, …) that `ENV` selects
# via src/config/env_config.resolve_config_path. These two helpers offer that as
# a scaffold-time choice, shared here so every Python service tier (mvc-*, ddd-*,
# and any future one) inherits identical behaviour from one place.
#
# Usage in a scaffold:
#   prompt_env_wise_config                 # sets INCLUDE_ENV_WISE (true|false)
#   ...
#   copy_global_config "$PROJECT_PATH"     # ships the plain inputs/outputs.yaml
#   apply_env_wise_config "$PROJECT_PATH"  # splits them into dev/prd if chosen

prompt_env_wise_config() {
    local answer
    read -r -p "Use env-wise config (inputs_dev/prd.yaml, outputs_dev/prd.yaml) instead of single files? [y/N]: " answer || true
    case "${answer:-}" in
        y | Y | yes | YES)
            INCLUDE_ENV_WISE=true
            print_status "config" "Env-wise config: inputs_dev/prd.yaml + outputs_dev/prd.yaml (ENV selects)"
            ;;
        *)
            INCLUDE_ENV_WISE=false
            print_status "config" "Config: single inputs.yaml + outputs.yaml (default)"
            ;;
    esac
}

apply_env_wise_config() {
    # When env-wise was chosen, split each plain config file into _dev/_prd copies
    # and remove the plain file — so env_config.resolve_config_path switches to
    # env-wise mode (an unknown ENV then fails loud). No-op otherwise. Idempotent
    # and safe under `set -u` (INCLUDE_ENV_WISE may be unset → treated as false).
    local project_path="$1"
    [[ "${INCLUDE_ENV_WISE:-false}" == "true" ]] || return 0

    local config_dir="$project_path/src/config"
    local kind
    for kind in inputs outputs; do
        if [[ -f "$config_dir/$kind.yaml" ]]; then
            cp "$config_dir/$kind.yaml" "$config_dir/${kind}_dev.yaml"
            cp "$config_dir/$kind.yaml" "$config_dir/${kind}_prd.yaml"
            rm -f "$config_dir/$kind.yaml"
        fi
    done
    print_status "success" "Env-wise config generated (dev/prd); plain inputs/outputs.yaml removed"
}

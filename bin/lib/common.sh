#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/common.sh is meant to be sourced, not executed." >&2
    exit 1
fi

if [ -n "${_BX_COMMON_LOADED:-}" ]; then
    return 0
fi
_BX_COMMON_LOADED=1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

PROMPT_PRIMARY='\033[1;34m'
PROMPT_SUB='\033[1;35m'
# shellcheck disable=SC2034
CANCEL="$PROMPT_SUB"

prompt_main() {
    printf "${PROMPT_PRIMARY}[?]${NC} %s" "$1"
}

prompt_sub() {
    printf "    ${PROMPT_SUB}└${NC} %s" "$1"
}

prompt_can_read() {
    [ -t 0 ] || [ "${BLUEPRINTX_STDIN_ANSWERS:-}" = "1" ]
}

prompt_warn_default() {
    local str_question
    str_question="$(printf '%s' "$1" | sed -E $'s/\x1b\\[[0-9;]*m//g; s/[[:space:]]*(\\[[^]]*\\])?:?[[:space:]]*$//')"
    printf 'stdin is not a terminal; using %s for "%s" (set BLUEPRINTX_STDIN_ANSWERS=1 to answer from stdin)\n' \
        "${2:-its default}" "$str_question" >&2
}

prompt_read() {
    local _prompt_read_value=""
    if prompt_can_read; then
        read -r -p "$2" _prompt_read_value || true
    else
        prompt_warn_default "$2" "${3:-}"
    fi
    printf -v "$1" '%s' "$_prompt_read_value"
}

prompt_yes_no() {
    local var_name="$1"
    local rendered_prompt="$2"
    local default="${3:-n}"
    local answer=""

    prompt_read answer "$rendered_prompt" "'$default'"

    case "$answer" in
        y | Y | yes | YES) printf -v "$var_name" 'true' ;;
        n | N | no | NO) printf -v "$var_name" 'false' ;;
        *)
            if [ "$default" = "y" ]; then
                printf -v "$var_name" 'true'
            else
                printf -v "$var_name" 'false'
            fi
            ;;
    esac
}

if [ -n "${NO_COLOR:-}" ]; then
    BRAND_TEAL=''
    BRAND_PINK=''
    BRAND_NC=''
elif command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 256 ]; then
    BRAND_TEAL='\033[38;5;73m'
    BRAND_PINK='\033[38;5;169m'
    BRAND_NC="$NC"
else
    # shellcheck disable=SC2034
    BRAND_TEAL="$CYAN"
    # shellcheck disable=SC2034
    BRAND_PINK="$MAGENTA"
    # shellcheck disable=SC2034
    BRAND_NC="$NC"
fi

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
            echo -e "${YELLOW}[?]${NC} ${message}" >&2
            echo "print_status: unknown status '${status}' — expected one of:" \
                "success|error|warning|info|config|debug|section" >&2
            ;;
    esac

    if [ -n "${LOG_FILE:-}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$status] $message" >> "$LOG_FILE"
    fi
}

print_section() {
    local title="$1"
    print_status "section" "$title"
}

exit_error() {
    local message="$1"
    local code="${2:-1}"
    print_status "error" "$message"
    exit "$code"
}

sed_inplace() {
    local -a arr_operands=()
    local str_arg
    for str_arg in "$@"; do
        [[ -f "$str_arg" ]] && arr_operands+=("$str_arg")
    done

    local str_suffix=".bpxbak$$"
    local int_status=0
    sed "-i${str_suffix}" "$@" || int_status=$?

    for str_arg in "${arr_operands[@]}"; do
        [[ -f "${str_arg}${str_suffix}" ]] && rm -f "${str_arg}${str_suffix}"
    done

    return "$int_status"
}

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

prompt_env_wise_config() {
    prompt_yes_no INCLUDE_ENV_WISE \
        "$(prompt_main "Use env-wise config (inputs_dev/prd.yaml, outputs_dev/prd.yaml) instead of single files? [y/N]: ")"
    if [ "$INCLUDE_ENV_WISE" = "true" ]; then
        print_status "config" "Env-wise config: inputs_dev/prd.yaml + outputs_dev/prd.yaml (ENV selects)"
    else
        print_status "config" "Config: single inputs.yaml + outputs.yaml (default)"
    fi
}

strip_bump_version() {
    local project_path="$1"
    python3 - "$project_path/poe_tasks.toml" <<'PY'
import re
import sys

path_tasks = sys.argv[1]

with open(path_tasks, encoding="utf-8") as fh:
    text = fh.read()

# Remove the task's leading comment run, its table header, and its key lines.
#
# Anchored on STRUCTURE, never on comment wording, for the same reason the Makefile
# version was: a reworded comment must not silently defeat the strip. The comment run
# `(?:#[^\n]*\n)*` is bounded by the header line that follows it, and the body runs to
# the next top-level `[` table (or end of file). A blank line inside the body would end
# it early, so the body pattern accepts blank lines but not a new table header.
text = re.sub(
    r"\n(?:#[^\n]*\n)*\[tool\.poe\.tasks\.bump_version\]\n(?:(?!\[)[^\n]*\n)*",
    "\n",
    text,
    count=1,
)

if "bump_version" in text:
    raise SystemExit(f"strip_bump_version: bump_version still present in {path_tasks}")

with open(path_tasks, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

add_poe_include() {
    local project_path="$1"
    local include_file="$2"
    python3 - "$project_path/poe_tasks.toml" "$include_file" <<'PY_INNER'
import re
import sys

path_tasks, str_include = sys.argv[1], sys.argv[2]

with open(path_tasks, encoding="utf-8") as fh:
    text = fh.read()

if f'"{str_include}"' in text:
    sys.exit(0)

cls_match = re.search(r"\n\[tool\.poe\]\ninclude = \[([^\]]*)\]\n", text)
if cls_match:
    str_existing = cls_match.group(1).strip()
    str_entries = f'{str_existing}, "{str_include}"' if str_existing else f'"{str_include}"'
    text = text[: cls_match.start()] + f"\n[tool.poe]\ninclude = [{str_entries}]\n" + text[cls_match.end() :]
else:
    text = text.rstrip("\n") + f'\n\n[tool.poe]\ninclude = ["{str_include}"]\n'

with open(path_tasks, "w", encoding="utf-8") as fh:
    fh.write(text)
PY_INNER
}

apply_env_wise_config() {
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

scaffold_purge_caches() {
    local project_path="$1"
    [ -d "$project_path" ] || return 0

    find "$project_path" -type d \
        \( -name '__pycache__' -o -name '.pytest_cache' \
        -o -name '.ruff_cache' -o -name '.mypy_cache' \) \
        -prune -exec rm -rf {} + 2>/dev/null || true
    find "$project_path" -type f -name '*.py[cod]' -delete 2>/dev/null || true
}

to_import_package_name() {
    local str_dist="$1"
    printf '%s' "${str_dist//-/_}"
}

is_valid_project_name() {
    local str_name="$1"
    [[ "$str_name" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]
}

copy_repo_rules_provisioner() {
    local project_path="$1"
    local required_checks_src="$2"
    local blueprintx_root
    blueprintx_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    mkdir -p "$project_path/bin/lib"
    cp "$blueprintx_root/templates/common/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$blueprintx_root/templates/python-common/bin/enable_repo_rules.sh" \
        "$project_path/bin/enable_repo_rules.sh"
    cp "$required_checks_src" "$project_path/bin/required-checks.txt"
    chmod +x "$project_path/bin/enable_repo_rules.sh"
}

copy_dependabot_auto_merge() {
    local project_path="$1" common_root
    common_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/templates/common"
    mkdir -p "$project_path/.github/workflows" "$project_path/bin"
    cp "$common_root/.github/workflows/dependabot-auto-merge.yml" "$project_path/.github/workflows/"
    cp "$common_root/bin/dependabot_auto_merge.sh" "$project_path/bin/"
    chmod +x "$project_path/bin/dependabot_auto_merge.sh"
}

copy_repo_policy_workflows() {
    local project_path="$1"
    local common_root
    common_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/templates/common"
    mkdir -p "$project_path/.github/workflows" "$project_path/bin"
    local str_wf
    for str_wf in close-linked-issues branch-has-issue pr-title-conventional \
        pr-body-template pr-self-assign; do
        cp "$common_root/.github/workflows/$str_wf.yml" "$project_path/.github/workflows/"
    done
    cp "$common_root/bin/close_linked_issues.sh" "$common_root/bin/check_pr_policy.sh" \
        "$project_path/bin/"
    chmod +x "$project_path/bin/close_linked_issues.sh" "$project_path/bin/check_pr_policy.sh"
    copy_dependabot_auto_merge "$project_path"
}

remove_repo_policy_scripts() {
    local project_path="$1"
    rm -f "$project_path/bin/close_linked_issues.sh" "$project_path/bin/check_pr_policy.sh" \
        "$project_path/bin/dependabot_auto_merge.sh"
}

# shellcheck source=bin/lib/scaffold_comment_budget.sh
source "$(dirname "${BASH_SOURCE[0]}")/scaffold_comment_budget.sh"

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
            # A typo'd status used to land here and print an UNMARKED line, so a warning
            # rendered exactly like neutral output — measured: 35 calls spelled "warn"
            # instead of "warning" across the five Python scaffolds, every one of them a
            # warning the user could not tell apart from ordinary chatter. Nothing in the
            # repo uses this branch deliberately (every status in use is in the list
            # above), so it now names the bad status on stderr instead of swallowing it.
            echo -e "${YELLOW}[?]${NC} ${message}" >&2
            echo "print_status: unknown status '${status}' — expected one of:" \
                "success|error|warning|info|config|debug|section" >&2
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

# ============================================================================
# ============================================================================
# strip_bump_version — remove the hand-bump task from the copied poe_tasks.toml
# ============================================================================
#
# Usage:
#   strip_bump_version "$project_path"
#
# Meaningless once versioning is tag-driven (lib: poetry-dynamic-versioning;
# services: the release.yaml workflow) — it would bump a frozen "0.0.0" stub.
# Call only on the ONLINE path; offline scaffolds keep the task (cz bump).
# Shared by every Python scaffold so the regex lives in one place.
#
# Before the poe migration this edited BOTH the Makefile and tasks.sh, in three
# places each (.PHONY / recipe / help, then function / case branch / help) — six
# regexes for one removal, which is what two implementations of one command list
# costs even at deletion time. One TOML table replaces all six.

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

# ============================================================================
# add_poe_include — wire a conditional poe task file into poe_tasks.toml
# ============================================================================
#
# Usage:
#   add_poe_include "$project_path" "poe_tasks.offline.toml"
#
# The Makefile declared both conditional fragments unconditionally as
# `-include make/*.mk`, whose leading '-' made a missing file silent. Poe's
# `include` is NOT equivalent: a missing path does not fail the run, but it
# DOES print `Warning: Poe could not include file from invalid path …` on every
# invocation — measured. An online, non-library project would print two warnings
# before every `poe lint`, which is how a team learns to read past warnings.
#
# So the include list names only the fragments actually copied, appended here at
# scaffold time. Idempotent: re-adding the same file is a no-op, and a second
# distinct file extends the existing list rather than opening a second
# `[tool.poe]` table (which would be invalid TOML).

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

scaffold_purge_caches() {
    # Strip interpreter/tool caches from a freshly generated tree.
    #
    # The scaffolds copy template trees with `cp -r`, which has no exclusion
    # mechanism, so any __pycache__ / .pytest_cache / .ruff_cache / .mypy_cache
    # left in templates/ by a local tool run is copied straight into the new
    # project. CI cannot see it — a fresh checkout has no caches — and the
    # generated .gitignore then hides the result from `git status` downstream,
    # so it ships silently from a maintainer's machine and nowhere else.
    #
    # Purging once, after the copy phase, keeps ONE implementation instead of an
    # exclusion argument repeated at ~30 `cp -r` call sites (and needs no rsync).
    local project_path="$1"
    [ -d "$project_path" ] || return 0

    find "$project_path" -type d \
        \( -name '__pycache__' -o -name '.pytest_cache' \
        -o -name '.ruff_cache' -o -name '.mypy_cache' \) \
        -prune -exec rm -rf {} + 2>/dev/null || true
    find "$project_path" -type f -name '*.py[cod]' -delete 2>/dev/null || true
}

to_import_package_name() {
    # Derive the Python IMPORT package name from a distribution name (blueprintx#113).
    #
    # A PyPI *distribution* name may contain hyphens; a Python *import package* may
    # not — a hyphen is an operator, so `from my-lib.thing import x` is a parse-time
    # SyntaxError. Conflating the two writes `src/my-lib/` and every deep import
    # inside the generated package fails to compile.
    #
    # It hides unusually well, which is why it survived: the top-level `__init__`
    # compiles either way (it has nothing to import from itself), and
    # `importlib.import_module("my-lib")` succeeds on the string form. Only a
    # submodule import written as SOURCE actually breaks — so the smoke test that
    # catches it has to reach past the top level.
    local str_dist="$1"
    printf '%s' "${str_dist//-/_}"
}

is_valid_project_name() {
    # A project name must survive both identities: a hyphenated dist name AND the
    # underscored import package derived from it. Rejecting here is the whole fix
    # for names no substitution can rescue (a leading digit, a dot, a space).
    local str_name="$1"
    [[ "$str_name" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]
}

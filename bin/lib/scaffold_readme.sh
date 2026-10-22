#!/usr/bin/env bash

if [ -n "${_BX_SCAFFOLD_README_LOADED:-}" ]; then
    return 0
fi
_BX_SCAFFOLD_README_LOADED=1

readonly STR_LINKEDIN_PLACEHOLDER_URL="https://www.linkedin.com/in/your-linkedin-handle"
readonly STR_README_VARS='${README_ARCHETYPE} ${LINKEDIN_URL} ${AUTHOR_NAME} ${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_DISPLAY_NAME} ${GITHUB_USERNAME} ${PROJECT_LICENSE} ${STATE_MANAGEMENT_VARIANT}'

resolve_linkedin_url() {
    local str_input

    if [ -n "${LINKEDIN_URL:-}" ]; then
        print_status "config" "LinkedIn URL (env): $LINKEDIN_URL"
        return
    fi

    if [ -t 0 ]; then
        prompt_read str_input "$(prompt_main "LinkedIn profile URL or handle (empty keeps a placeholder the README gate flags): ")"
        case "$str_input" in
            "") ;;
            *linkedin.com/in/*) LINKEDIN_URL="$str_input" ;;
            *) LINKEDIN_URL="https://www.linkedin.com/in/${str_input#@}" ;;
        esac
    fi

    if [ -z "${LINKEDIN_URL:-}" ]; then
        LINKEDIN_URL="$STR_LINKEDIN_PLACEHOLDER_URL"
        print_status "warning" "LinkedIn URL not set; README gets the placeholder $LINKEDIN_URL (export LINKEDIN_URL to fix)"
        return
    fi
    print_status "config" "LinkedIn URL: $LINKEDIN_URL"
}

scaffold_filter_archetype_blocks() {
    local str_archetype="$1"

    awk -v keep="$str_archetype" '
        /^<!--[[:space:]]*only:/ {
            list = $0
            sub(/^<!--[[:space:]]*only:[[:space:]]*/, "", list); sub(/[[:space:]]*-->.*$/, "", list)
            n = split(list, names, /[[:space:]]+/); show = 0
            for (i = 1; i <= n; i++) if (names[i] == keep) show = 1
            in_block = 1; next
        }
        /^<!--[[:space:]]*\/only[[:space:]]*-->/ { in_block = 0; next }
        !in_block || show { print }
    '
}

scaffold_render_readme() {
    local str_skeleton_dir="$1"
    local path_template="$2"
    local path_dest="$3"
    local str_meta="$BLUEPRINTX_ROOT/templates/$str_skeleton_dir/skeleton.meta"

    README_ARCHETYPE="$(sed -n 's/^readme_archetype=//p' "$str_meta" | head -n1)"
    if [ -z "$README_ARCHETYPE" ]; then
        print_status "error" "templates/$str_skeleton_dir/skeleton.meta has no readme_archetype="
        return 1
    fi
    resolve_linkedin_url

    AUTHOR_NAME="${AUTHOR_NAME:-$GITHUB_USERNAME}"
    PROJECT_LICENSE="${PROJECT_LICENSE:-${LICENSE_CHOICE:-}}"
    export README_ARCHETYPE LINKEDIN_URL AUTHOR_NAME PROJECT_LICENSE PROJECT_NAME PROJECT_DESCRIPTION \
        PROJECT_DISPLAY_NAME GITHUB_USERNAME STATE_MANAGEMENT_VARIANT

    scaffold_filter_archetype_blocks "$README_ARCHETYPE" <"$path_template" \
        | envsubst "$STR_README_VARS" >"$path_dest"
}

scaffold_copy_readme_gate() {
    local path_project="$1"
    local path_common="$BLUEPRINTX_ROOT/templates/common/bin"

    mkdir -p "$path_project/bin/lib"
    cp "$path_common/check_readme_structure.sh" "$path_project/bin/check_readme_structure.sh"
    cp "$path_common/lib/md_structure.sh" "$path_project/bin/lib/md_structure.sh"
    chmod +x "$path_project/bin/check_readme_structure.sh"
}

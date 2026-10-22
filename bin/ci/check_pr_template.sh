#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=templates/common/bin/lib/md_structure.sh
source "$REPO_ROOT/templates/common/bin/lib/md_structure.sh"

readonly -a ARR_OPTIONAL=("F:Additional Notes/Dependencies" "F:Additional Notes/Follow-up")
readonly -a ARR_CHANGE_GROUP=("F:Changes Made/Added" "F:Changes Made/Updated" "F:Changes Made/Fixed")
readonly -a ARR_TESTING_PAIR=("3:Testing/Manual Testing" "3:Testing/Automated Testing")
readonly STR_NOT_APPLICABLE="F:Testing/Not Applicable"
readonly STR_CHANGES_SECTION="2:Changes Made"
readonly STR_SEP=$'\037'

declare -a ARR_TPL_KEYS=() ARR_BODY_KEYS=()
declare -A MAP_TPL_LINES=() MAP_BODY_LINES=() MAP_BODY_PAR=() MAP_REAL=() MAP_PH=()
declare -a ARR_PROBLEMS=()

parse_layout() {
    awk -v sep="$STR_SEP" '
        function trim(s) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", s); return s }
        function see(k, p) { if (!(k in seen)) { seen[k] = 1; par[k] = p; keys[++nk] = k } }
        function add(s,   t, own) {
            gsub(/\t/, " ", s); t = trim(s); if (t == "") return
            own = (fld != "") ? fld : (h3 != "") ? h3 : h2
            if (own == "") return
            lines[own] = lines[own] (lines[own] == "" ? "" : sep) t
        }
        /^## [^#]/  { h2n = trim(substr($0, 4)); h2 = "2:" h2n; h3 = ""; fld = ""; see(h2, ""); next }
        /^### [^#]/ { h3 = "3:" h2n "/" trim(substr($0, 5)); fld = ""; see(h3, h2); next }
        /^---[[:space:]]*$/ { next }
        /^\*\*[^*]+\*\*[[:space:]]*:/ || /^\*\*[^*]+:\*\*/ {
            rest = $0; sub(/^\*\*/, "", rest); name = rest
            if (rest ~ /^[^*]+:\*\*/) { sub(/:\*\*.*$/, "", name); sub(/^[^*]+:\*\*/, "", rest) }
            else { sub(/\*\*[[:space:]]*:.*$/, "", name); sub(/^[^*]+\*\*[[:space:]]*:/, "", rest) }
            h3 = ""; fld = "F:" h2n "/" trim(name); see(fld, h2); add(rest); next
        }
        { add($0) }
        END { for (i = 1; i <= nk; i++) { k = keys[i]; printf "%s\t%s\t%s\n", k, (par[k] == "" ? "-" : par[k]), lines[k] } }
    '
}

load_layout() {
    local str_kind="$1" path_file="$2" str_key str_par str_lines
    while IFS=$'\t' read -r str_key str_par str_lines; do
        if [ "$str_kind" = "template" ]; then
            MAP_TPL_LINES["$str_key"]="$str_lines"
            ARR_TPL_KEYS+=("$str_key")
        else
            MAP_BODY_LINES["$str_key"]="$str_lines"
            MAP_BODY_PAR["$str_key"]="$str_par"
            ARR_BODY_KEYS+=("$str_key")
        fi
    done < <(md_normalize <"$path_file" | parse_layout)
}

tally_body() {
    local str_key str_line str_up
    local -a arr_lines
    for str_key in "${ARR_BODY_KEYS[@]}"; do
        MAP_PH["$str_key"]="${MAP_PH[$str_key]:-0}"
        MAP_REAL["$str_key"]="${MAP_REAL[$str_key]:-0}"
    done
    for str_key in "${ARR_BODY_KEYS[@]}"; do
        IFS="$STR_SEP" read -ra arr_lines <<<"${MAP_BODY_LINES[$str_key]}"
        for str_line in "${arr_lines[@]}"; do
            [[ "$str_line" =~ ^[-*][[:space:]]+\*\*[^*]+\*\*[[:space:]]*:$ ]] && continue
            if [[ "$STR_SEP${MAP_TPL_LINES[$str_key]:-}$STR_SEP" == *"$STR_SEP$str_line$STR_SEP"* ]]; then
                MAP_PH["$str_key"]=$((MAP_PH[$str_key] + 1))
                continue
            fi
            for str_up in "$str_key" "${MAP_BODY_PAR[$str_key]}"; do
                if [ "$str_up" != "-" ]; then
                    MAP_REAL["$str_up"]=$((MAP_REAL[$str_up] + 1))
                fi
            done
        done
    done
}

describe() {
    local str_name="${1#*:}"
    str_name="${str_name##*/}"
    case "${1%%:*}" in
        2) printf '`## %s` heading' "$str_name" ;;
        3) printf '`### %s` heading' "$str_name" ;;
        *) printf '`**%s**:` field' "$str_name" ;;
    esac
}

problem() { ARR_PROBLEMS+=("$1"); }

is_filled() {
    local str_key="$1"
    [ -n "${MAP_REAL[$str_key]+x}" ] || return 1
    [ "${MAP_REAL[$str_key]}" -gt 0 ] && [ "${MAP_PH[$str_key]}" -eq 0 ]
}

why_unfilled() {
    local str_key="$1"
    if [ -z "${MAP_REAL[$str_key]+x}" ]; then
        printf 'missing — not found at the start of a line (a list marker, indent or "> " quote hides it)'
    elif [ "${MAP_PH[$str_key]}" -gt 0 ]; then
        printf 'still the template text — replace it with this PR'"'"'s own content'
    else
        printf 'present but empty — fill it in, or say why it does not apply'
    fi
}

in_list() {
    local str_needle="$1" str_item
    shift
    for str_item in "$@"; do [ "$str_item" = "$str_needle" ] && return 0; done
    return 1
}

check_registry_is_current() {
    local str_key
    for str_key in "${ARR_OPTIONAL[@]}" "${ARR_CHANGE_GROUP[@]}" "${ARR_TESTING_PAIR[@]}" \
        "$STR_NOT_APPLICABLE" "$STR_CHANGES_SECTION"; do
        if [ -z "${MAP_TPL_LINES[$str_key]+x}" ]; then
            print_status "error" "gate registry is stale: $(describe "$str_key") is no longer in the template — update bin/ci/check_pr_template.sh"
            exit 2
        fi
    done
}

check_mandatory() {
    local str_key
    for str_key in "${ARR_TPL_KEYS[@]}"; do
        in_list "$str_key" "${ARR_OPTIONAL[@]}" "${ARR_CHANGE_GROUP[@]}" \
            "${ARR_TESTING_PAIR[@]}" "$STR_NOT_APPLICABLE" && continue
        is_filled "$str_key" || problem "$(describe "$str_key"): $(why_unfilled "$str_key")"
    done
}

check_change_group() {
    local str_key
    for str_key in "${ARR_CHANGE_GROUP[@]}"; do is_filled "$str_key" && return 0; done
    problem "$(describe "$STR_CHANGES_SECTION" | sed 's/heading/section/'): none of Added, Updated or Fixed is filled in — a PR changes something, name it"
}

check_testing() {
    local str_key bool_need_na=0
    for str_key in "${ARR_TESTING_PAIR[@]}"; do
        is_filled "$str_key" && continue
        bool_need_na=1
        if ! is_filled "$STR_NOT_APPLICABLE"; then
            problem "$(describe "$str_key"): $(why_unfilled "$str_key"); fill it, or explain why under a filled $(describe "$STR_NOT_APPLICABLE")"
        fi
    done
    if [ "$bool_need_na" -eq 0 ] && [ -n "${MAP_REAL[$STR_NOT_APPLICABLE]+x}" ]; then
        is_filled "$STR_NOT_APPLICABLE" || problem "$(describe "$STR_NOT_APPLICABLE"): $(why_unfilled "$STR_NOT_APPLICABLE")"
    fi
}

check_optional_not_filler() {
    local str_key
    for str_key in "${ARR_OPTIONAL[@]}" "${ARR_CHANGE_GROUP[@]}"; do
        [ -n "${MAP_PH[$str_key]+x}" ] || continue
        if [ "${MAP_PH[$str_key]}" -gt 0 ]; then
            problem "$(describe "$str_key"): still the template text — fill it in or delete it"
        fi
    done
    for str_key in "${ARR_OPTIONAL[@]}"; do
        [ -n "${MAP_REAL[$str_key]+x}" ] || continue
        if [ "${MAP_REAL[$str_key]}" -eq 0 ] && [ "${MAP_PH[$str_key]}" -eq 0 ]; then
            problem "$(describe "$str_key"): present but empty — fill it in or delete it"
        fi
    done
}

usage() {
    print_status "error" "usage: check_pr_template.sh --body-file FILE|- [--author LOGIN] [--template FILE]"
    exit 2
}

main() {
    local path_body="" str_author="" path_template="$REPO_ROOT/.github/PULL_REQUEST_TEMPLATE.md"
    while [ $# -gt 0 ]; do
        case "$1" in
            --body-file) path_body="${2:-}"; shift 2 || usage ;;
            --author) str_author="${2:-}"; shift 2 || usage ;;
            --template) path_template="${2:-}"; shift 2 || usage ;;
            *) usage ;;
        esac
    done
    [ -n "$path_body" ] || usage
    [ -r "$path_template" ] || { print_status "error" "template unreadable: $path_template"; exit 2; }
    if [ "$path_body" = "-" ]; then path_body="/dev/stdin"; fi
    [ -r "$path_body" ] || { print_status "error" "PR body unreadable: $path_body"; exit 2; }

    if [[ "$str_author" == *"[bot]" ]]; then
        print_status "info" "author $str_author is a bot: it cannot write the prose fields, layout check skipped"
        exit 0
    fi

    load_layout template "$path_template"
    check_registry_is_current
    load_layout body "$path_body"
    tally_body
    check_mandatory
    check_change_group
    check_testing
    check_optional_not_filler

    if [ "${#ARR_PROBLEMS[@]}" -eq 0 ]; then
        print_status "success" "PR body matches the template layout (${#ARR_TPL_KEYS[@]} elements derived from the template)"
        exit 0
    fi
    local str_problem
    for str_problem in "${ARR_PROBLEMS[@]}"; do print_status "error" "$str_problem"; done
    print_status "error" "${#ARR_PROBLEMS[@]} problem(s). See CONTRIBUTING.md -> 'PR template layout' for which fields are mandatory."
    exit 1
}

main "$@"

#!/usr/bin/env bash
# Checks a PR body against the layout .github/PULL_REQUEST_TEMPLATE.md declares
# (blueprintx#587): every `##`/`###` heading and `**Label**:` field the template carries must
# appear at line start with real content, bar the conditional ones recorded below. The
# contract is walked out of the template, never hardcoded; only the mandatory-versus-
# conditional split, which syntax cannot tell us, is data here. Rationale and the rule a
# human reads: CONTRIBUTING.md -> "PR template layout".
#
# Usage: check_pr_template.sh --body-file FILE|- [--author LOGIN] [--template FILE]
# Exit: 0 clean or bot-exempt, 1 layout problems, 2 unusable input (never a silent pass).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

# Keys are "<kind>:<name>": 2 = `##`, 3 = `###`, F = `**Name**:` field at line start.
readonly -a ARR_OPTIONAL=("F:Dependencies" "F:Follow-up")
readonly -a ARR_CHANGE_GROUP=("F:Added" "F:Updated" "F:Fixed")
readonly -a ARR_TESTING_PAIR=("3:Manual Testing" "3:Automated Testing")
readonly STR_NOT_APPLICABLE="F:Not Applicable"
readonly STR_CHANGES_SECTION="2:Changes Made"

declare -a ARR_TPL_KEYS=()
declare -A MAP_TPL_COUNT=() MAP_TPL_TEXT=() MAP_BODY_COUNT=() MAP_BODY_TEXT=()
declare -a ARR_PROBLEMS=()

normalize() {
    # Drops CRs, HTML comments (multi-line) and fenced code: none of it is layout.
    tr -d '\r' | awk '
        BEGIN { in_comment = 0; in_fence = 0 }
        {
            line = $0; out = ""
            while (length(line) > 0) {
                if (in_comment) {
                    p = index(line, "-->")
                    if (p == 0) { line = ""; break }
                    line = substr(line, p + 3); in_comment = 0
                } else {
                    p = index(line, "<!--")
                    if (p == 0) { out = out line; line = ""; break }
                    out = out substr(line, 1, p - 1); line = substr(line, p + 4); in_comment = 1
                }
            }
            if (out ~ /^[[:space:]]*```/) { in_fence = !in_fence; next }
            if (!in_fence) print out
        }'
}

parse_layout() {
    # stdin: normalized markdown. Prints "KEY<TAB>content-lines<TAB>joined-text" per node,
    # in first-seen order. A heading or label line itself is not content.
    awk '
        function trim(s) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", s); return s }
        function see(k) { if (!(k in seen)) { seen[k] = 1; keys[++nk] = k } }
        function add(s,   t) {
            t = trim(s); if (t == "") return
            if (h2 != "") { cnt[h2]++; txt[h2] = txt[h2] (txt[h2] == "" ? "" : " ") t }
            if (h3 != "") { cnt[h3]++; txt[h3] = txt[h3] (txt[h3] == "" ? "" : " ") t }
            if (fld != "") { cnt[fld]++; txt[fld] = txt[fld] (txt[fld] == "" ? "" : " ") t }
        }
        /^## [^#]/  { h2 = "2:" trim(substr($0, 4)); h3 = ""; fld = ""; see(h2); next }
        /^### [^#]/ { h3 = "3:" trim(substr($0, 5)); fld = ""; see(h3); next }
        /^---[[:space:]]*$/ { h3 = ""; fld = ""; next }
        /^\*\*[^*]+\*\*:/ {
            rest = $0; sub(/^\*\*/, "", rest); name = rest; sub(/\*\*:.*$/, "", name)
            sub(/^[^*]+\*\*:/, "", rest)
            fld = "F:" trim(name); see(fld); add(rest); next
        }
        { add($0) }
        END { for (i = 1; i <= nk; i++) { k = keys[i]; printf "%s\t%d\t%s\n", k, cnt[k] + 0, txt[k] } }
    '
}

load_layout() {
    # $1 = template|body, $2 = file. Fills the MAP_TPL_* or MAP_BODY_* pair.
    local str_kind="$1" path_file="$2" str_key int_n str_text
    while IFS=$'\t' read -r str_key int_n str_text; do
        if [ "$str_kind" = "template" ]; then
            MAP_TPL_COUNT["$str_key"]="$int_n"
            MAP_TPL_TEXT["$str_key"]="$str_text"
            ARR_TPL_KEYS+=("$str_key")
        else
            MAP_BODY_COUNT["$str_key"]="$int_n"
            MAP_BODY_TEXT["$str_key"]="$str_text"
        fi
    done < <(normalize <"$path_file" | parse_layout)
}

describe() {
    case "${1%%:*}" in
        2) printf '`## %s` heading' "${1#*:}" ;;
        3) printf '`### %s` heading' "${1#*:}" ;;
        *) printf '`**%s**:` field' "${1#*:}" ;;
    esac
}

problem() { ARR_PROBLEMS+=("$1"); }

is_filled() {
    # Present, non-empty, and not the template's own text left in place.
    local str_key="$1"
    [ -n "${MAP_BODY_COUNT[$str_key]+x}" ] || return 1
    [ "${MAP_BODY_COUNT[$str_key]}" -gt 0 ] || return 1
    [ "${MAP_BODY_TEXT[$str_key]:-}" != "${MAP_TPL_TEXT[$str_key]:-}" ] \
        || [ -z "${MAP_TPL_TEXT[$str_key]:-}" ]
}

why_unfilled() {
    local str_key="$1"
    if [ -z "${MAP_BODY_COUNT[$str_key]+x}" ]; then
        printf 'missing — the template declares it, and it must appear at the start of a line'
    elif [ "${MAP_BODY_COUNT[$str_key]}" -eq 0 ]; then
        printf 'present but empty — fill it in, or say why it does not apply'
    else
        printf 'still the template text — replace it with this PR'"'"'s own content'
    fi
}

in_list() {
    local str_needle="$1" str_item
    shift
    for str_item in "$@"; do [ "$str_item" = "$str_needle" ] && return 0; done
    return 1
}

check_registry_is_current() {
    # A classification naming a label the template no longer has would rot silently.
    local str_key
    for str_key in "${ARR_OPTIONAL[@]}" "${ARR_CHANGE_GROUP[@]}" "${ARR_TESTING_PAIR[@]}" \
        "$STR_NOT_APPLICABLE" "$STR_CHANGES_SECTION"; do
        if [ -z "${MAP_TPL_COUNT[$str_key]+x}" ]; then
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
    # Not Applicable is required exactly when a testing subsection is not filled in.
    local str_key bool_need_na=0
    for str_key in "${ARR_TESTING_PAIR[@]}"; do
        is_filled "$str_key" && continue
        bool_need_na=1
        if ! is_filled "$STR_NOT_APPLICABLE"; then
            problem "$(describe "$str_key"): $(why_unfilled "$str_key"); fill it, or explain why under a filled $(describe "$STR_NOT_APPLICABLE")"
        fi
    done
    if [ "$bool_need_na" -eq 0 ] && [ -n "${MAP_BODY_COUNT[$STR_NOT_APPLICABLE]+x}" ]; then
        is_filled "$STR_NOT_APPLICABLE" || problem "$(describe "$STR_NOT_APPLICABLE"): $(why_unfilled "$STR_NOT_APPLICABLE")"
    fi
}

check_optional_not_filler() {
    # Absent is fine; the template's own placeholder left in place looks answered but is not.
    local str_key
    for str_key in "${ARR_OPTIONAL[@]}" "${ARR_CHANGE_GROUP[@]}"; do
        [ -n "${MAP_BODY_COUNT[$str_key]+x}" ] || continue
        [ "${MAP_BODY_COUNT[$str_key]}" -gt 0 ] || continue
        if [ "${MAP_BODY_TEXT[$str_key]}" = "${MAP_TPL_TEXT[$str_key]}" ]; then
            problem "$(describe "$str_key"): still the template text — fill it in or delete it"
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

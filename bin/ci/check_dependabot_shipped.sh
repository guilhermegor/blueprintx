#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

int_failures=0

fail() {
    echo "ERROR: $*" >&2
    int_failures=$((int_failures + 1))
}

skeleton_meta_files() {
    ls "$REPO_ROOT"/templates/*/skeleton.meta
}

meta_field() {
    grep "^$2=" "$1" | cut -d= -f2-
}

copy_source() {
    local str_script="$1" str_line str_src str_var str_dir
    str_line="$(grep -vE '^[[:space:]]*#' "$str_script" \
        | grep -E "GITHUB_USERNAME=\"\\\$GITHUB_USERNAME\" envsubst '\\\$\{GITHUB_USERNAME\}' .*dependabot\.yml.* \"?\\\$\{?project_path\}?/\.github/dependabot\.yml" | head -1)"
    [ -n "$str_line" ] || return 1
    str_src="$(sed -E 's/.*< *"([^"]+)".*/\1/' <<<"$str_line")"
    str_var="$(sed -E 's#^\$\{?([A-Z_]+)\}?/.*#\1#' <<<"$str_src")"
    str_dir="$(sed -nE "s#^${str_var}=\"\\\$BLUEPRINTX_ROOT/(templates/[a-z-]+)\"\$#\\1#p" "$str_script")"
    printf '%s/%s\n' "$REPO_ROOT/$str_dir" "${str_src#*/}"
}

cooldown_per_block() {
    awk '
        /^  - package-ecosystem:/ { if (int_in && int_n != 1) int_bad = 1; int_in = 1; int_n = 0; int_blocks++ }
        /^    cooldown:/ { int_n++ }
        END { if (int_in && int_n != 1) int_bad = 1; exit (int_blocks > 0 && !int_bad) ? 0 : 1 }
    ' "$1"
}

assignees_per_block() {
    awk '
        /^  - package-ecosystem:/ { if (int_in && int_n != 1) int_bad = 1; int_in = 1; int_n = 0; int_blocks++ }
        /^    assignees:/ { int_a = 1; next }
        int_a && /^      - / { if ($0 ~ /^      - "[$][{]GITHUB_USERNAME[}]"[[:space:]]*$/) int_n++; else int_bad = 1; next }
        { int_a = 0 }
        END { if (int_in && int_n != 1) int_bad = 1; exit (int_blocks > 0 && !int_bad) ? 0 : 1 }
    ' "$1"
}

check_promote() {
    local str_promote="$REPO_ROOT/bin/promote_offline_to_online.sh" str_bad
    [ -f "$str_promote" ] || { fail "promote_offline_to_online.sh is missing"; return; }
    str_bad="$(grep -vE '^[[:space:]]*#' "$str_promote" | awk '
        /^copy_online_assets_[a-z_]+\(\)/ { str_fn = $1; int_n[str_fn] += 0; next }
        /^}/ { str_fn = ""; next }
        /dependabot\.yml/ {
            if (str_fn == "") { print "outside a copy_online_assets_* function: " $0; next }
            if ($0 ~ /GITHUB_USERNAME="[$]GITHUB_USERNAME" envsubst [\047][$][{]GITHUB_USERNAME[}][\047] <[[:space:]]*"[^"]*dependabot[.]yml" *> *"[^"]*[.]github[/]dependabot[.]yml"/) int_n[str_fn]++
            else print str_fn " has a render without the inline owner or the dependabot.yml source: " $0
        }
        END { for (k in int_n) if (int_n[k] != 1) print k " renders dependabot.yml " int_n[k] " time(s), expected 1" }
    ')"
    [ -z "$str_bad" ] || fail "promote_offline_to_online.sh renders: $str_bad"
}

check_static() {
    local str_meta str_script str_src
    while IFS= read -r str_meta; do
        str_script="$REPO_ROOT/$(meta_field "$str_meta" scaffold)"
        str_src="$(copy_source "$str_script")" \
            || { fail "$(basename "$str_script") never copies dependabot.yml through envsubst"; continue; }
        [ -f "$str_src" ] || { fail "$(basename "$str_script") copies missing file ${str_src#"$REPO_ROOT"/}"; continue; }
        cooldown_per_block "$str_src" \
            || fail "${str_src#"$REPO_ROOT"/} needs exactly one cooldown on every ecosystem"
        assignees_per_block "$str_src" \
            || fail "${str_src#"$REPO_ROOT"/} needs the \${GITHUB_USERNAME} assignee on every ecosystem"
    done < <(skeleton_meta_files)
    check_promote
}

usage() {
    echo "usage: $0 --static" >&2
    exit 2
}

main() {
    [ "${1:-}:$#" = "--static:1" ] || usage
    check_static
    [ "$int_failures" -eq 0 ] || exit 1
    echo "OK: every skeleton ships a dependabot.yml with a cooldown and an assignee."
}

main "$@"

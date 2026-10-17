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
        | grep -E '\bcp .*dependabot\.yml.* "?\$\{?project_path\}?/\.github/dependabot\.yml' | head -1)"
    [ -n "$str_line" ] || return 1
    str_src="$(sed -E 's/.*\bcp +"([^"]+)".*/\1/' <<<"$str_line")"
    str_var="$(sed -E 's#^\$\{?([A-Z_]+)\}?/.*#\1#' <<<"$str_src")"
    str_dir="$(sed -nE "s#^${str_var}=\"\\\$BLUEPRINTX_ROOT/(templates/[a-z-]+)\"\$#\\1#p" "$str_script")"
    printf '%s/%s\n' "$REPO_ROOT/$str_dir" "${str_src#*/}"
}

check_static() {
    local str_meta str_script str_src
    while IFS= read -r str_meta; do
        str_script="$REPO_ROOT/$(meta_field "$str_meta" scaffold)"
        str_src="$(copy_source "$str_script")" \
            || { fail "$(basename "$str_script") never copies dependabot.yml"; continue; }
        [ -f "$str_src" ] || { fail "$(basename "$str_script") copies missing file ${str_src#"$REPO_ROOT"/}"; continue; }
        [ "$(grep -c '^  - package-ecosystem:' "$str_src")" -eq "$(grep -c '^    cooldown:' "$str_src")" ] \
            || fail "${str_src#"$REPO_ROOT"/} sets no cooldown on every ecosystem"
    done < <(skeleton_meta_files)
}

usage() {
    echo "usage: $0 --static" >&2
    exit 2
}

main() {
    [ "${1:-}:$#" = "--static:1" ] || usage
    check_static
    [ "$int_failures" -eq 0 ] || exit 1
    echo "OK: every skeleton ships a dependabot.yml with a cooldown."
}

main "$@"

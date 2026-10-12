#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"

MANIFEST="$REPO_ROOT/templates/common/review-config.manifest"
int_failures=0

fail() {
    echo "ERROR: $*" >&2
    int_failures=$((int_failures + 1))
}

manifest_paths() {
    sed -E 's/[[:space:]]+$//; s#/+$##; /^[[:space:]]*(#|$)/d' "$MANIFEST"
}

skeleton_meta_files() {
    local str_only="${1:-}" str_meta
    for str_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
        [ -z "$str_only" ] || [ "$(basename "$(dirname "$str_meta")")" = "$str_only" ] || continue
        printf '%s\n' "$str_meta"
    done
}

meta_field() {
    grep "^$2=" "$1" | cut -d= -f2-
}

check_content() {
    :
}

script_text() {
    local str_script="$1" str_lib
    cat "$str_script"
    { grep -oE 'source "\$SCRIPT_DIR/\.\./lib/[A-Za-z0-9_]+\.sh"' "$str_script" || true; } \
        | sed -E 's#.*/lib/([A-Za-z0-9_]+\.sh)"#\1#' \
        | while IFS= read -r str_lib; do cat "$REPO_ROOT/bin/lib/$str_lib"; done
}

copy_commands() {
    local str_text str_var str_dir
    str_text="$(script_text "$1" | awk '!/^[[:space:]]*#/ { if (sub(/\\$/, "")) printf "%s ", $0; else print }')"
    while IFS='=' read -r str_var str_dir; do
        str_text="$(sed -E "s#\\\$\{?${str_var}\}?#${str_dir}#g" <<<"$str_text")"
    done < <(sed -nE 's#^([A-Z_]+)="\$BLUEPRINTX_ROOT/(templates/[a-z-]+)"$#\1=\2#p' <<<"$str_text")
    { grep -oE '(^|[^[:alnum:]_./-])cp( +-[-A-Za-z]+)* +[^ ]+ +[^ ]+' <<<"$str_text" || true; } \
        | sed -E 's#^[^c]*cp#cp#; s#"##g'
}

copy_matches() {
    local str_path="$2" str_dir="$2" str_src str_dst str_flag="" str_tok
    local -a list_tok
    read -ra list_tok <<<"$1"
    for str_tok in "${list_tok[@]:1}"; do
        case "$str_tok" in
            -*) str_flag="$str_flag$str_tok" ;;
            *) if [ -z "${str_src:-}" ]; then str_src="$str_tok"; else str_dst="$str_tok"; fi ;;
        esac
    done
    str_src="${str_src%/.}"
    str_src="${str_src%/}"
    if [ "$str_src" = "templates/common/$str_path" ] && [[ "${str_dst%/}" == */"$str_path" ]]; then
        return 0
    fi
    [[ "$str_flag" =~ ^-[a-zA-Z]*[rRa] || "$str_flag" == *--recursive* || "$str_flag" == *--archive* ]] \
        || return 1
    [ "$str_src" != "templates/common" ] || return 0
    while [[ "$str_dir" == */* ]]; do
        str_dir="${str_dir%/*}"
        [ "$str_src" = "templates/common/$str_dir" ] && return 0
    done
    return 1
}

copies_path() {
    local str_cmd
    while IFS= read -r str_cmd; do
        copy_matches "$str_cmd" "$2" && return 0
    done <<<"$1"
    return 1
}

check_static() {
    local str_meta str_script str_path str_cmds
    while IFS= read -r str_path; do
        [ -e "$REPO_ROOT/templates/common/$str_path" ] \
            || fail "manifest path '$str_path' does not exist under templates/common/"
    done < <(manifest_paths)
    while IFS= read -r str_meta; do
        str_script="$REPO_ROOT/$(meta_field "$str_meta" scaffold)"
        str_cmds="$(copy_commands "$str_script")"
        while IFS= read -r str_path; do
            copies_path "$str_cmds" "$str_path" \
                || fail "$(basename "$str_script") never copies '$str_path'"
        done < <(manifest_paths)
    done < <(skeleton_meta_files)
}

check_project() {
    local str_project="$1" str_path
    while IFS= read -r str_path; do
        [ -e "$str_project/$str_path" ] || fail "generated project lacks '$str_path'"
    done < <(manifest_paths)
    check_content "$str_project"
}

scaffold_skeleton() {
    local str_name="$1" str_scaffold="$2" str_work="$3"
    if spec_skeleton_supported "$str_name"; then
        spec_stdin_for_skeleton "$str_name" "" \
            | GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
                "$str_work" ci-scaffold "CI review-config check" "0.0.1" >/dev/null
    else
        GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
            "$str_work" ci-scaffold "CI review-config check" "0.0.1" \
            < <(printf '\n%.0s' {1..100}) >/dev/null
    fi
}

check_generated() {
    local str_meta str_name str_work int_before
    local int_seen=0
    export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot
    export GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com
    while IFS= read -r str_meta; do
        str_name="$(basename "$(dirname "$str_meta")")"
        int_seen=$((int_seen + 1))
        str_work="$(mktemp -d)"
        int_before=$int_failures
        if scaffold_skeleton "$str_name" "$(meta_field "$str_meta" scaffold)" "$str_work"; then
            check_project "$str_work/ci-scaffold"
        else
            fail "scaffolding '$str_name' failed"
        fi
        rm -rf "$str_work"
        [ "$int_failures" -gt "$int_before" ] && echo "  FAIL $str_name" || echo "  ok   $str_name"
    done < <(skeleton_meta_files "${1:-}")
    [ "$int_seen" -gt 0 ] || { echo "ERROR: no skeleton named '${1:-}'" >&2; exit 2; }
}

usage() {
    echo "usage: $0 --static | --generated [--skeleton <name>] | --project <dir>" >&2
    exit 2
}

main() {
    [ -f "$MANIFEST" ] || { echo "ERROR: $MANIFEST missing" >&2; exit 1; }
    [ -n "$(manifest_paths)" ] || { echo "ERROR: $MANIFEST lists no paths" >&2; exit 1; }
    case "${1:-}:$#" in
        --static:1) check_static ;;
        --generated:1) check_generated "" ;;
        --generated:3) [ "$2" = "--skeleton" ] && [ -n "$3" ] || usage; check_generated "$3" ;;
        --project:2) check_project "$2" ;;
        *) usage ;;
    esac
    [ "$int_failures" -eq 0 ] || exit 1
    echo "OK: every skeleton ships the review config in $(basename "$MANIFEST")."
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"
source "$REPO_ROOT/bin/lib/no_background_git.sh"

int_failures=0

fail() {
    echo "ERROR: $*" >&2
    int_failures=$((int_failures + 1))
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

nav_pages() {
    awk '/^nav:/ { in_nav = 1; next } /^[A-Za-z_]/ { in_nav = 0 } in_nav' "$1" \
        | { grep -oE '[A-Za-z0-9_./-]+\.md' || true; } | sort -u
}

script_refs() {
    { grep -hoE '(^|[ "'\''=(])(\./)?bin/[A-Za-z0-9_./-]+\.(sh|py)' "$@" || true; } \
        | sed -E 's#^[ "'\''=(]##; s#^\./##' | sort -u
}

check_project() {
    local str_project="$1" str_ref str_file
    local -a list_sources=()
    if [ -f "$str_project/mkdocs.yml" ]; then
        while IFS= read -r str_ref; do
            [ -e "$str_project/docs/$str_ref" ] \
                || fail "mkdocs.yml nav lists docs/$str_ref, which the scaffold never copied"
        done < <(nav_pages "$str_project/mkdocs.yml")
    fi
    for str_file in "$str_project/poe_tasks.toml" "$str_project/.pre-commit-config.yaml" \
        "$str_project"/.github/workflows/*.yml; do
        [ -f "$str_file" ] && list_sources+=("$str_file")
    done
    [ "${#list_sources[@]}" -gt 0 ] || return 0
    for str_file in "${list_sources[@]}"; do
        while IFS= read -r str_ref; do
            [ -e "$str_project/$str_ref" ] \
                || fail "${str_file#"$str_project"/} runs $str_ref, which the scaffold never copied"
        done < <(script_refs "$str_file")
    done
}

scaffold_skeleton() {
    local str_name="$1" str_scaffold="$2" str_work="$3"
    if spec_skeleton_supported "$str_name"; then
        spec_stdin_for_skeleton "$str_name" "" \
            | BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
                "$str_work" ci-scaffold "CI reference check" "0.0.1" >/dev/null
    else
        GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
            "$str_work" ci-scaffold "CI reference check" "0.0.1" \
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
    echo "usage: $0 --generated [--skeleton <name>] | --project <dir>" >&2
    exit 2
}

main() {
    case "${1:-}:$#" in
        --generated:1) check_generated "" ;;
        --generated:3) [ "$2" = "--skeleton" ] && [ -n "$3" ] || usage; check_generated "$3" ;;
        --project:2) check_project "$2" ;;
        *) usage ;;
    esac
    [ "$int_failures" -eq 0 ] || exit 1
    echo "OK: every nav page and bin/ script a generated project references exists."
}

main "$@"

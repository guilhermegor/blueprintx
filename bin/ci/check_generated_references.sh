#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"
source "$REPO_ROOT/bin/lib/no_background_git.sh"

int_failures=0
str_current_work=""

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
        | { grep -vE '^[[:space:]]*#|https?://' || true; } \
        | { grep -oE '[A-Za-z0-9_./-]+\.md' || true; } | sort -u
}

docs_dir() {
    local str_dir
    str_dir="$(sed -nE 's/^docs_dir:[[:space:]]*["'\'']?([^"'\''[:space:]]+).*/\1/p' "$1" | head -1)"
    printf '%s' "${str_dir:-docs}"
}

script_refs() {
    { grep -hvE '^[[:space:]]*#' "$@" || true; } \
        | { grep -oE '(^|[ "'\''=(])(\./)?bin/[A-Za-z0-9_./-]+\.(sh|py)' || true; } \
        | sed -E 's#^[ "'\''=(]##; s#^\./##' | sort -u
}

check_project() {
    local str_project="$1" str_ref str_file
    local int_refs=0
    local -a list_sources=()
    local str_docs
    [ -d "$str_project" ] || { fail "no project directory at $str_project"; return 0; }
    if [ -f "$str_project/mkdocs.yml" ]; then
        str_docs="$(docs_dir "$str_project/mkdocs.yml")"
        while IFS= read -r str_ref; do
            int_refs=$((int_refs + 1))
            [ -e "$str_project/$str_docs/$str_ref" ] \
                || fail "mkdocs.yml nav lists $str_docs/$str_ref, which the scaffold never copied"
        done < <(nav_pages "$str_project/mkdocs.yml")
    fi
    for str_file in "$str_project/poe_tasks.toml" "$str_project/.pre-commit-config.yaml" \
        "$str_project/package.json" "$str_project/Makefile" "$str_project"/make/*.mk \
        "$str_project"/.github/workflows/*.y*ml "$str_project"/.github/actions/*/action.y*ml; do
        [ -f "$str_file" ] && list_sources+=("$str_file")
    done
    for str_file in "${list_sources[@]}"; do
        while IFS= read -r str_ref; do
            int_refs=$((int_refs + 1))
            [ -e "$str_project/$str_ref" ] \
                || fail "${str_file#"$str_project"/} runs $str_ref, which the scaffold never copied"
        done < <(script_refs "$str_file")
    done
    [ "$int_refs" -gt 0 ] || fail "no nav page or bin/ script reference found in $str_project; nothing was checked"
}

scaffold_skeleton() {
    local str_name="$1" str_scaffold="$2" str_work="$3"
    if spec_skeleton_supported "$str_name"; then
        BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
            "$str_work" ci-scaffold "CI reference check" "0.0.1" \
            <<<"$(spec_stdin_for_skeleton "$str_name" "")" >>"$str_work.log" 2>&1
    else
        GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
            "$str_work" ci-scaffold "CI reference check" "0.0.1" \
            < <(printf '\n%.0s' {1..100}) >>"$str_work.log" 2>&1
    fi
}

check_generated() {
    local str_meta str_name str_work int_before
    local int_seen=0
    unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE
    export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot
    export GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com
    while IFS= read -r str_meta; do
        str_name="$(basename "$(dirname "$str_meta")")"
        int_seen=$((int_seen + 1))
        str_work="$(mktemp -d)"
        str_current_work="$str_work"
        trap 'rm -rf "${str_current_work:-}" "${str_current_work:-}.log"' EXIT
        int_before=$int_failures
        if scaffold_skeleton "$str_name" "$(meta_field "$str_meta" scaffold)" "$str_work"; then
            check_project "$str_work/ci-scaffold"
        else
            fail "scaffolding '$str_name' failed; last output:"
            tail -20 "$str_work.log" >&2
        fi
        rm -rf "$str_work" "$str_work.log"
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

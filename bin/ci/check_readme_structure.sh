#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GATE="$REPO_ROOT/templates/common/bin/check_readme_structure.sh"
# shellcheck source=bin/lib/spec.sh
source "$REPO_ROOT/bin/lib/spec.sh"

check_static() {
    local int_rc=0
    cd "$REPO_ROOT"
    bash "$GATE" README.md || int_rc=1
    bash "$GATE" --template templates/common/README.template.md templates/*/README.md || int_rc=1
    return "$int_rc"
}

scaffold_skeleton() {
    local str_name="$1" str_scaffold="$2" path_work="$3"
    export LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
    if spec_skeleton_supported "$str_name"; then
        spec_stdin_for_skeleton "$str_name" "" \
            | BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
                "$path_work" ci-scaffold "CI README check" "0.0.1" >/dev/null
    else
        GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
            "$path_work" ci-scaffold "CI README check" "0.0.1" \
            < <(printf '\n%.0s' {1..100}) >/dev/null
    fi
}

check_generated() {
    local path_meta str_name str_scaffold path_work path_project int_rc=0
    for path_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
        str_name="$(basename "$(dirname "$path_meta")")"
        str_scaffold="$(sed -n 's/^scaffold=//p' "$path_meta")"
        path_work="$(mktemp -d)"
        path_project="$path_work/ci-scaffold"
        if ! scaffold_skeleton "$str_name" "$str_scaffold" "$path_work"; then
            echo "[x] $str_name: the scaffold itself failed" >&2
            int_rc=1
        elif [ ! -f "$path_project/bin/check_readme_structure.sh" ]; then
            echo "[x] $str_name: the generated project does not ship bin/check_readme_structure.sh" >&2
            int_rc=1
        elif ! bash "$path_project/bin/check_readme_structure.sh" "$path_project/README.md"; then
            echo "[x] $str_name: the generated README fails its own gate" >&2
            int_rc=1
        fi
        rm -rf "$path_work"
    done
    return "$int_rc"
}

case "${1:-}" in
    --generated) check_generated ;;
    "") check_static ;;
    *) echo "usage: check_readme_structure.sh [--generated]" >&2; exit 2 ;;
esac

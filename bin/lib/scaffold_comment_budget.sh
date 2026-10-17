#!/usr/bin/env bash

scaffold_comment_budget() {
    local project_path="$1" blueprintx_root str_name
    blueprintx_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    mkdir -p "$project_path/bin"
    for str_name in check_comment_budget.py comment_budget_allowlist.txt; do
        cp "$blueprintx_root/templates/python-common/bin/$str_name" "$project_path/bin/$str_name"
    done
    cp "$blueprintx_root/templates/common/bin/comment_budget_routing.txt" \
        "$project_path/bin/comment_budget_routing.txt"
    rm -f "$project_path/comment_budget_baseline.txt"
    python3 "$project_path/bin/check_comment_budget.py" --root "$project_path" --write-baseline ||
        exit_error "Could not write comment_budget_baseline.txt for $project_path"
}

scaffold_comment_budget_refresh() {
    [ -f "$1/comment_budget_baseline.txt" ] || return 0
    [ ! -e "$1/.git" ] || git -C "$1" add -A
    scaffold_comment_budget "$1"
}

#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=bin/lib/common.sh
source "bin/lib/common.sh"

str_pattern='sed[[:space:]]+-i([[:space:]]|'\'''\''|"")'

mapfile -t arr_files < <(
    {
        find bin -name '*.sh'
        find templates -type d -name bin -exec find {} -name '*.sh' \;
    } | sort -u
)

arr_hits=()
for str_file in "${arr_files[@]}"; do
    while IFS=: read -r int_lineno str_content; do
        [[ "$str_content" =~ ^[[:space:]]*# ]] && continue
        arr_hits+=("${str_file}:${int_lineno}:${str_content}")
    done < <(grep -nE "$str_pattern" "$str_file")
done

if [ "${#arr_hits[@]}" -gt 0 ]; then
    print_status "error" "Bare -i flag on sed found (breaks BSD/macOS sed, blueprintx#459)."
    print_status "error" "Use sed_inplace (bin/lib/common.sh) or sed -i.bak ... && rm -f *.bak instead:"
    printf '%s\n' "${arr_hits[@]}" >&2
    exit 1
fi

print_status "success" "No bare -i flag on sed under bin/ or templates/**/bin/"

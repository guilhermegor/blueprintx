#!/bin/bash
# Rejects a bare `sed -i` (GNU-only: takes no argument) anywhere under bin/ or
# templates/**/bin/ — BSD/macOS sed's -i REQUIRES an argument, so the same call aborts a
# scaffold partway through on the platform the README advertises (blueprintx#459).
#
# The portable form is sed_inplace() (bin/lib/common.sh) or an explicit
# `sed -i.bak ... && rm -f *.bak`. Without this gate the 31st site lands the next time
# someone copies an existing sed -i line — the same "partial sweep becomes precedent"
# failure check_comment_language.py was built to stop.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=bin/lib/common.sh
source "bin/lib/common.sh"

# A real invocation always has whitespace right after -i (the script or the next flag).
# sed -i.bak (sed_inplace's own portable form) has no whitespace there, so it never matches.
str_pattern='sed[[:space:]]+-i[[:space:]]'

mapfile -t arr_files < <(
    {
        find bin -name '*.sh'
        find templates -type d -name bin -exec find {} -name '*.sh' \;
    } | sort -u
)

arr_hits=()
for str_file in "${arr_files[@]}"; do
    while IFS=: read -r int_lineno str_content; do
        # Skip comment lines (prose explaining the pattern, not an actual invocation).
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

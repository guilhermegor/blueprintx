#!/usr/bin/env bash
# Validates every templates/*/skeleton.meta:
#   1. All four required fields are present and non-empty.
#   2. The scaffold= path exists relative to repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATES_DIR="$REPO_ROOT/templates"
REQUIRED_FIELDS=(language display_name description scaffold)
errors=0

for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    skeleton_dir="$(basename "$(dirname "$meta")")"
    echo "Checking: templates/$skeleton_dir/skeleton.meta"

    for field in "${REQUIRED_FIELDS[@]}"; do
        value="$(grep "^${field}=" "$meta" | cut -d= -f2- | tr -d '[:space:]')"
        if [ -z "$value" ]; then
            echo "  ERROR: field '$field' is missing or empty" >&2
            errors=$((errors + 1))
        fi
    done

    scaffold_rel="$(grep '^scaffold=' "$meta" | cut -d= -f2-)"
    if [ -n "$scaffold_rel" ] && [ ! -f "$REPO_ROOT/$scaffold_rel" ]; then
        echo "  ERROR: scaffold path does not exist: $scaffold_rel" >&2
        errors=$((errors + 1))
    fi
done

if [ "$errors" -gt 0 ]; then
    echo "validate_meta: $errors error(s) found." >&2
    exit 1
fi

echo "validate_meta: all skeleton.meta files are valid."

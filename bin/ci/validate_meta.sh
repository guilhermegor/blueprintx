#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATES_DIR="$REPO_ROOT/templates"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
REQUIRED_FIELDS=(language display_name description scaffold)
CHECK_README="$REPO_ROOT/templates/common/bin/check_readme_structure.sh"
errors=0

if [ ! -f "$CLAUDE_MD" ]; then
    echo "ERROR: $CLAUDE_MD not found — cannot check skeleton documentation" >&2
    errors=$((errors + 1))
fi

for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    skeleton_dir="$(basename "$(dirname "$meta")")"
    echo "Checking: templates/$skeleton_dir/skeleton.meta"

    for field in "${REQUIRED_FIELDS[@]}"; do
        value="$(grep "^${field}=" "$meta" | cut -d= -f2- | tr -d '[:space:]' || true)"
        if [ -z "$value" ]; then
            echo "  ERROR: field '$field' is missing or empty" >&2
            errors=$((errors + 1))
        fi
    done

    scaffold_rel="$(grep '^scaffold=' "$meta" | cut -d= -f2- || true)"
    if [ -n "$scaffold_rel" ] && [ ! -f "$REPO_ROOT/$scaffold_rel" ]; then
        echo "  ERROR: scaffold path does not exist: $scaffold_rel" >&2
        errors=$((errors + 1))
    fi

    str_archetype="$(grep '^readme_archetype=' "$meta" | cut -d= -f2- | tr -d '[:space:]' || true)"
    if [ -n "$str_archetype" ] && ! bash "$CHECK_README" --list-archetypes | grep -qxF -- "$str_archetype"; then
        echo "  ERROR: readme_archetype '$str_archetype' is not one of: $(bash "$CHECK_README" --list-archetypes | tr '\n' ' ')" >&2
        errors=$((errors + 1))
    fi

    if [ -f "$CLAUDE_MD" ] && ! grep -qF -- "$skeleton_dir" "$CLAUDE_MD"; then
        echo "  ERROR: skeleton '$skeleton_dir' is not mentioned in CLAUDE.md" >&2
        errors=$((errors + 1))
    fi
done

if [ "$errors" -gt 0 ]; then
    echo "validate_meta: $errors error(s) found." >&2
    exit 1
fi

echo "validate_meta: all skeleton.meta files are valid."

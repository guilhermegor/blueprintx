#!/usr/bin/env bash
# Validates every templates/*/skeleton.meta:
#   1. All four required fields are present and non-empty.
#   2. The scaffold= path exists relative to repo root.
#   3. The skeleton's own directory name is mentioned in the root CLAUDE.md — a live
#      skeleton (discoverable in the `make new` menu via its skeleton.meta) undocumented
#      in CLAUDE.md is exactly the blueprintx#478 gap: a brief written from CLAUDE.md's
#      skeleton list alone silently under-counts the scaffolding surface by one skeleton.
#      Machine-decidable ("is this substring present"), so it is a gate, not a review
#      question — CLAUDE.md's own QUALITY of the mention stays a human call.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATES_DIR="$REPO_ROOT/templates"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
REQUIRED_FIELDS=(language display_name description scaffold)
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
        # `|| true`: under `set -euo pipefail` a missing key makes grep exit 1 and kills the
        # whole gate BEFORE the check below can name the field. Measured: exit 1 with no
        # message at all, which every should-fail test read as proof the check had run.
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

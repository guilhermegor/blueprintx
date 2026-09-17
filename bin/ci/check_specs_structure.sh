#!/usr/bin/env bash
# Validates the .specs/ layout (blueprintx#447), matching the same one-implementation
# pattern as every other gate in this repo (see the root CLAUDE.md): a bin/ci/*.sh script
# both the root pre-commit hook and scaffold_checks.yml CI call.
#
# Rules (see .specs/CLAUDE.md for the human-facing version):
#   1. If .specs/ exists, .specs/CLAUDE.md must exist.
#   2. The only allowed top-level entries under .specs/ are CLAUDE.md, features/, _lessons/.
#   3. Every entry directly under .specs/features/ must be a directory.
#   4. Every .specs/features/<name>/ must contain at least one of design.md or plan.md.
#   5. _lessons/ has no content requirement — it is machine-populated and git-ignored.
#
# Root-repo-only: .specs/ is a BlueprintX convention for this repo's own specs/plans, not
# a scaffolded-project concept, so this script is not part of templates/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SPECS_DIR="$REPO_ROOT/.specs"
errors=0

# No .specs/ at all is not an error — it's simply not adopted yet.
if [ ! -d "$SPECS_DIR" ]; then
    echo "check_specs_structure: no .specs/ directory — nothing to check."
    exit 0
fi

if [ ! -f "$SPECS_DIR/CLAUDE.md" ]; then
    echo "ERROR: .specs/ exists but .specs/CLAUDE.md is missing" >&2
    errors=$((errors + 1))
fi

for entry in "$SPECS_DIR"/*; do
    name="$(basename "$entry")"
    case "$name" in
        CLAUDE.md|features|_lessons) ;;
        *)
            echo "ERROR: unexpected top-level entry .specs/$name (only CLAUDE.md, features/, _lessons/ are allowed)" >&2
            errors=$((errors + 1))
            ;;
    esac
done

if [ -d "$SPECS_DIR/features" ]; then
    for entry in "$SPECS_DIR/features"/*; do
        [ -e "$entry" ] || continue
        name="$(basename "$entry")"
        if [ ! -d "$entry" ]; then
            echo "ERROR: .specs/features/$name is not a directory" >&2
            errors=$((errors + 1))
            continue
        fi
        if [ ! -f "$entry/design.md" ] && [ ! -f "$entry/plan.md" ]; then
            echo "ERROR: .specs/features/$name has neither design.md nor plan.md" >&2
            errors=$((errors + 1))
        fi
    done
fi

if [ "$errors" -gt 0 ]; then
    echo "check_specs_structure: $errors error(s) found." >&2
    exit 1
fi

echo "check_specs_structure: .specs/ layout is valid."

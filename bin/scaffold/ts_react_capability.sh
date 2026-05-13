#!/usr/bin/env bash
# Create a new capability inside a scaffolded blueprintx React project.
#
# Adds the standard layer directory structure (domain, application,
# infrastructure, ui) and the thin per-layer CLAUDE.md files that
# @-import the shared rules from src/capabilities/_layers/.
#
# Usage:
#   bash ts_react_capability.sh <capability-name> [project-root]
#
# Examples:
#   # From inside a scaffolded project root
#   bash ~/github/blueprintx/bin/scaffold/ts_react_capability.sh billing
#
#   # Targeting a specific project root
#   bash ts_react_capability.sh notifications /path/to/project

set -euo pipefail

# --- Args --------------------------------------------------------------------

CAPABILITY_NAME="${1:-}"
PROJECT_ROOT="${2:-$(pwd)}"

if [[ -z "$CAPABILITY_NAME" ]]; then
    echo "ERROR: capability name required" >&2
    echo "Usage: $0 <capability-name> [project-root]" >&2
    exit 1
fi

if [[ ! "$CAPABILITY_NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "ERROR: capability name must be lowercase kebab-case (got: '$CAPABILITY_NAME')" >&2
    echo "Allowed: a-z, 0-9, hyphen. Must start with a letter." >&2
    exit 1
fi

# Reserved names (would collide with the shared layer rules dir or example)
case "$CAPABILITY_NAME" in
    _layers|example)
        echo "ERROR: '$CAPABILITY_NAME' is reserved" >&2
        exit 1
        ;;
esac

# --- Paths -------------------------------------------------------------------

CAPABILITIES_DIR="$PROJECT_ROOT/src/capabilities"
LAYERS_DIR="$CAPABILITIES_DIR/_layers"
NEW_CAP_DIR="$CAPABILITIES_DIR/$CAPABILITY_NAME"

# --- Preflight ---------------------------------------------------------------

if [[ ! -d "$CAPABILITIES_DIR" ]]; then
    echo "ERROR: $CAPABILITIES_DIR not found." >&2
    echo "Are you inside a blueprintx-scaffolded React project?" >&2
    exit 1
fi

if [[ ! -d "$LAYERS_DIR" ]]; then
    echo "ERROR: $LAYERS_DIR not found." >&2
    echo "" >&2
    echo "This project was scaffolded before _layers/ existed." >&2
    echo "Copy it from the blueprintx template:" >&2
    echo "  cp -r <blueprintx>/templates/react-spa-webpack/src/capabilities/_layers \\" >&2
    echo "        $CAPABILITIES_DIR/_layers" >&2
    exit 1
fi

if [[ -e "$NEW_CAP_DIR" ]]; then
    echo "ERROR: capability already exists: $NEW_CAP_DIR" >&2
    exit 1
fi

# Sanity-check: all 4 layer rule files must be present before we generate
# imports that depend on them.
for layer in domain application infrastructure ui; do
    if [[ ! -f "$LAYERS_DIR/$layer.md" ]]; then
        echo "ERROR: missing $LAYERS_DIR/$layer.md" >&2
        echo "The @-import would resolve to nothing. Restore the file first." >&2
        exit 1
    fi
done

# --- Generate ----------------------------------------------------------------

for layer in domain application infrastructure ui; do
    mkdir -p "$NEW_CAP_DIR/$layer"
    cat > "$NEW_CAP_DIR/$layer/CLAUDE.md" <<EOF
@../../_layers/$layer.md

<!--
  Capability-specific notes for this layer go below the @import.
  The shared rules live in src/capabilities/_layers/$layer.md and are
  inlined above. Anything written below applies only to this capability.
-->
EOF
done

# --- Report ------------------------------------------------------------------

echo "✅ Capability '$CAPABILITY_NAME' created at:"
echo "   $NEW_CAP_DIR"
echo ""
echo "Generated structure:"
echo "   $CAPABILITY_NAME/"
echo "   ├── domain/CLAUDE.md         → @-imports _layers/domain.md"
echo "   ├── application/CLAUDE.md    → @-imports _layers/application.md"
echo "   ├── infrastructure/CLAUDE.md → @-imports _layers/infrastructure.md"
echo "   └── ui/CLAUDE.md             → @-imports _layers/ui.md"
echo ""
echo "Next steps:"
echo "   • domain/         → add entities.ts, enums.ts, ports.ts, dto.ts"
echo "   • application/    → add state.ts, actions.ts, reducer.ts, use-cases.ts"
echo "   • infrastructure/ → add adapters (one file per external system)"
echo "   • ui/             → add components/ and pages/"
echo "   • $CAPABILITY_NAME/index.ts        → public barrel (TaskContextProvider, pages)"
echo "   • $CAPABILITY_NAME/context.tsx     → React Context provider for state"
echo ""
echo "Layer-scoped CLAUDE.md files will auto-load when Claude Code edits"
echo "files inside the matching directory. Capability-specific notes can"
echo "be appended below the @-import in each layer's CLAUDE.md."

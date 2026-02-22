#!/usr/bin/env bash

set -euo pipefail

cat <<'EOF'
Usage: ./run.sh <target>
   or: make <target>

Targets (no make required):
  init          Run interactive BlueprintX scaffolder
  preview       Show available skeletons and examples
  dev           Scaffold into a temporary directory
  dev-clean     Scaffold into a temp directory and delete it on exit
  dry-run       Show structure only, no files created
  init-venv     Create local Poetry venv using .python-version (installs deps)
  update-venv   Update Poetry dependencies
  mkdocs-serve  Install docs deps (if needed) and serve with live reload
  help          Show this help
EOF

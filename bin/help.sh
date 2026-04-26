#!/usr/bin/env bash

set -euo pipefail

cat <<'EOF'
Usage: ./run.sh <target>
   or: make <target>

Targets (no make required):
  new           Run interactive BlueprintX scaffolder
  preview       Show available skeletons and examples
  dev           Scaffold into a temporary directory
  dev-clean     Scaffold into a temp directory and delete it on exit
  dry-run       Show structure only, no files created
  init_venv     Create local Poetry venv using .python-version (installs deps)
  update_venv   Update Poetry dependencies
  mkdocs_server  Install docs deps (if needed) and serve with live reload
  help          Show this help
EOF

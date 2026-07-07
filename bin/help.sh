#!/usr/bin/env bash

set -euo pipefail

cat <<'EOF'
Usage: ./tasks.sh <target>
   or: make <target>

Targets (no make required):
  new           Run interactive BlueprintX scaffolder
  install       Deploy bin/ + templates/ to /usr/share/blueprintx (needs sudo)
  preview       Show available skeletons and examples
  dev           Scaffold into a temporary directory
  dev-clean     Scaffold into a temp directory and delete it on exit
  dry-run       Show structure only, no files created
  init          Bootstrap venv + install pre-commit hooks (venv + precommit)
  venv          Create local Poetry venv using .python-version (installs deps)
  precommit     Install pre-commit hooks (pre-commit + commit-msg stages)
  lint          Run all pre-commit hooks across the repo (mirrors CI)
  update_venv   Update Poetry dependencies
  mkdocs_server  Install docs deps (if needed) and serve with live reload
  changelog     Regenerate root CHANGELOG.md from git tags (cz changelog)
  help          Show this help
EOF

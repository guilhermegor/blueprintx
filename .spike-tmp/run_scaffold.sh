#!/bin/bash
set -euo pipefail
REPO_ROOT="/home/guilhermegor/github/blueprintx/.claude/worktrees/agent-ad6c6903d972c6ab7"
WORK_DIR="$REPO_ROOT/.spike-tmp/work"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
printf 'n\n%.0s' {1..12} | GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/bin/scaffold/python_ddd_service.sh" \
	"$WORK_DIR" "pytho290" "Pythonpath spike" "0.0.1"

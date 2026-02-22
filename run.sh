#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { bash "$SCRIPT_DIR/scripts/help.sh"; }

cmd_init() { bash "$SCRIPT_DIR/scripts/blueprintx.sh"; }
cmd_preview() { bash "$SCRIPT_DIR/scripts/preview.sh"; }
cmd_dev() { bash "$SCRIPT_DIR/scripts/blueprintx.sh" --dev; }
cmd_dev_clean() { bash "$SCRIPT_DIR/scripts/blueprintx.sh" --dev --clean; }
cmd_dry_run() { bash "$SCRIPT_DIR/scripts/blueprintx.sh" --dry-run; }

cmd_init_venv() { bash "$SCRIPT_DIR/scripts/init_venv.sh"; }

cmd_update_venv() {
	poetry update
	echo "Poetry project updated"
}

cmd_mkdocs_serve() {
	poetry install --with docs
	poetry run mkdocs serve -a 0.0.0.0:8000 --livereload
}

main() {
	local target="${1:-help}"
	shift || true

	case "$target" in
		init) cmd_init ;;
		preview) cmd_preview ;;
		dev) cmd_dev ;;
		dev-clean|dev_clean) cmd_dev_clean ;;
		dry-run|dry_run) cmd_dry_run ;;
		init-venv|init_venv) cmd_init_venv ;;
		update-venv|update_venv) cmd_update_venv ;;
		mkdocs-serve|mkdocs_serve) cmd_mkdocs_serve ;;
		help|-h|--help) usage ;;
		*) echo "Unknown target: $target" >&2; usage >&2; exit 1 ;;
	esac
}

main "$@"

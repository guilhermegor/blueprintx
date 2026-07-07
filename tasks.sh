#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { bash "$SCRIPT_DIR/bin/help.sh"; }

cmd_new() { bash "$SCRIPT_DIR/bin/blueprintx.sh"; }

cmd_install() {
	sudo rsync -a --delete "$SCRIPT_DIR/bin/" /usr/share/blueprintx/bin/
	sudo rsync -a --delete "$SCRIPT_DIR/templates/" /usr/share/blueprintx/templates/
	echo "Installed to /usr/share/blueprintx"
}

cmd_preview() { bash "$SCRIPT_DIR/bin/preview.sh"; }
cmd_dev() { bash "$SCRIPT_DIR/bin/blueprintx.sh" --dev; }
cmd_dev_clean() { bash "$SCRIPT_DIR/bin/blueprintx.sh" --dev --clean; }
cmd_dry_run() { bash "$SCRIPT_DIR/bin/blueprintx.sh" --dry-run; }

cmd_update_licenses() { bash "$SCRIPT_DIR/bin/update_licenses.sh"; }

cmd_venv() { bash "$SCRIPT_DIR/bin/venv.sh"; }

cmd_precommit() {
	poetry run pre-commit install
	poetry run pre-commit install --hook-type commit-msg
}

cmd_init() {
	cmd_venv
	cmd_precommit
}

cmd_lint() { poetry run pre-commit run --all-files; }

cmd_update_venv() {
	poetry update
	echo "Poetry project updated"
}

cmd_mkdocs_serve() {
	poetry install --with docs
	poetry run mkdocs serve -a 0.0.0.0:8000 --livereload
}

# Regenerate the root CHANGELOG.md from the conventional-commit / git-tag history (mirrors
# `make changelog`). The docs Changelog page single-sources this file; do not hand-edit it.
cmd_changelog() {
	poetry run cz changelog
	echo "Regenerated CHANGELOG.md"
}

main() {
	local target="${1:-help}"
	shift || true

	case "$target" in
		new) cmd_new ;;
		install) cmd_install ;;
		preview) cmd_preview ;;
		dev) cmd_dev ;;
		dev-clean|dev_clean) cmd_dev_clean ;;
		dry-run|dry_run) cmd_dry_run ;;
		update_licenses) cmd_update_licenses ;;
		init) cmd_init ;;
		venv) cmd_venv ;;
		precommit) cmd_precommit ;;
		lint) cmd_lint ;;
		update_venv) cmd_update_venv ;;
		mkdocs_server|mkdocs_serve) cmd_mkdocs_serve ;;
		changelog) cmd_changelog ;;
		help|-h|--help) usage ;;
		*) echo "Unknown target: $target" >&2; usage >&2; exit 1 ;;
	esac
}

main "$@"

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

# Mirrors `make check_function_length`. Makefile and tasks.sh must stay in sync.
cmd_check_function_length() {
	python3 templates/python-common/bin/check_function_length.py --root .
}

# Mirrors the Makefile's `verify_tiers`. Extra argv is forwarded, so `./tasks.sh verify_tiers
# --jobs 1` serialises the run the same way `make verify_tiers JOBS=1` does.
cmd_verify_tiers() {
	# ⚠️ `JOBS` is translated here so BOTH entry points honour it. The Makefile already maps
	# `JOBS=1` to `--jobs 1`; `tasks.sh` forwarded only positional arguments, and the script
	# reads `--jobs` alone and never the environment — so `JOBS=1 ./tasks.sh verify_tiers` ran
	# at FULL concurrency while `bin/help.sh` promised it serialised. Silent, and in the
	# dangerous direction: the flag exists to debug a tier interactively.
	#
	# Translating beats documenting the divergence. Makefile and tasks.sh are two interfaces to
	# one command list and must not drift — a written sync rule was tried and had already been
	# broken when blueprintx#189 found it. An explicit `--jobs` still wins, so the escape hatch
	# in the script's own header keeps working. Raised by review on #277.
	if [ -n "${JOBS:-}" ] && [ "$#" -eq 0 ]; then
		set -- --jobs "$JOBS"
	fi
	bash "$SCRIPT_DIR/bin/ci/scaffold_lint_test_all.sh" "$@"
}

main() {
	local target="${1:-help}"
	shift || true

	# Each hyphenated alt (dev-clean, dry-run, mkdocs_server) is the pre-#365 spelling, kept
	# for one release so a script or muscle memory typing the old name still works.
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
		check_function_length) cmd_check_function_length ;;
		verify_tiers) cmd_verify_tiers "$@" ;;
		update_venv) cmd_update_venv ;;
		mkdocs_serve|mkdocs_server) cmd_mkdocs_serve ;;
		changelog) cmd_changelog ;;
		help|-h|--help) usage ;;
		*) echo "Unknown target: $target" >&2; usage >&2; exit 1 ;;
	esac
}

main "$@"

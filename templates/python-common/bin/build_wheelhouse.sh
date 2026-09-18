#!/usr/bin/env bash
# Build (or assemble) the project's offline wheelhouse — blueprintx#299, pieces 1-3 of #127.
# A corporate machine behind a TLS-inspecting proxy that blocks PyPI outright cannot install
# anything; PR #297 already makes that failure LOUD (verify_venv_imports.py). This script is
# the remedy: `poe wheelhouse` builds the payload on a machine WITH internet access, and
# `poe wheelhouse_assemble` reconstructs it on the OFFLINE target after it is copied over.
# See docs/offline-wheelhouse.md for the full workflow.
#
# The heavy logic (marker evaluation against a TARGET environment, zip/split/manifest,
# verify-and-refuse) lives in lib/wheelhouse_select.py — a heredoc is for inert text a
# script emits, not a program (see bin/CLAUDE.md). This file owns only the network I/O
# (poetry export, pip download) and orchestration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

# Piece 1: default destination is a SIBLING of the repo — outside it, never a `git add`
# candidate, survives a re-clone. Per-repo because sibling projects pin different versions.
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-$PROJECT_ROOT/../_wheels/$(basename "$PROJECT_ROOT")}"
WHEELHOUSE_PART_MB="${WHEELHOUSE_PART_MB:-45}"
SELECT_PY="$SCRIPT_DIR/lib/wheelhouse_select.py"

resolve_target_env() {
	TARGET_PYVER="${WHEELHOUSE_TARGET_PYTHON_VERSION:-}"
	[[ -z "$TARGET_PYVER" ]] && TARGET_PYVER="$("$PYTHON" -c 'import platform; print(platform.python_version())')"
	TARGET_SYSPLAT="${WHEELHOUSE_TARGET_SYS_PLATFORM:-}"
	[[ -z "$TARGET_SYSPLAT" ]] && TARGET_SYSPLAT="$("$PYTHON" -c 'import sys; print(sys.platform)')"
	TARGET_MACHINE="${WHEELHOUSE_TARGET_PLATFORM_MACHINE:-}"
	[[ -z "$TARGET_MACHINE" ]] && TARGET_MACHINE="$("$PYTHON" -c 'import platform; print(platform.machine())')"
	TARGET_IMPL="${WHEELHOUSE_TARGET_IMPLEMENTATION:-cpython}"
	print_status "config" "Target: python $TARGET_PYVER, $TARGET_SYSPLAT/$TARGET_MACHINE ($TARGET_IMPL)"
}

# Piece 2 continued: the native-db tiers ship pyodbc/oracledb/psycopg/mysql-connector-python
# UNCONDITIONALLY (the backend is chosen at RUNTIME from config, not at scaffold time) — this
# is the wheelhouse-only pruning DB_BACKEND enables (measured 65 MB -> 45 MB, blueprintx#299).
# A no-op for tiers that never carry more than one driver.
driver_prune_list() {
	local -A str_driver_of=(
		[postgresql]=psycopg [mysql]=mysql-connector-python
		[oracle]=oracledb [mssql]=pyodbc
	)
	DROP_PACKAGES=()
	[[ -z "${DB_BACKEND:-}" ]] && return 0
	local str_key
	for str_key in "${!str_driver_of[@]}"; do
		[[ "$str_key" == "$DB_BACKEND" ]] && continue
		DROP_PACKAGES+=("${str_driver_of[$str_key]}")
	done
}

export_and_select() {
	local path_export="$1" path_selected="$2"
	local -a args_drop=()
	local str_pkg

	print_status "info" "Exporting locked dependencies ..."
	OUTPUT_FILE="$path_export" bash "$SCRIPT_DIR/export_deps.sh" >/dev/null

	for str_pkg in "${DROP_PACKAGES[@]:-}"; do
		[[ -n "$str_pkg" ]] && args_drop+=(--drop "$str_pkg")
	done
	print_status "info" "Selecting requirements for the target environment ..."
	"$PYTHON" "$SELECT_PY" select \
		--requirements "$path_export" --out "$path_selected" \
		--target-python-version "$TARGET_PYVER" \
		--target-sys-platform "$TARGET_SYSPLAT" \
		--target-platform-machine "$TARGET_MACHINE" \
		--target-implementation "$TARGET_IMPL" \
		"${args_drop[@]}"
}

# Cross-platform builds (target differs from the build machine) need pip's OWN platform-tag
# vocabulary ("win_amd64", "manylinux2014_x86_64", ...) — passed through verbatim rather than
# re-derived here, since guessing it is exactly the maze `pip download --platform`'s own docs
# already own. Left unset, pip downloads for the BUILD machine's own platform/ABI (the common
# case: build and target are the same OS, only the network differs).
download_wheels() {
	local path_selected="$1" dir_wheels="$2"
	local -a args_pip=(-m pip download --no-deps --dest "$dir_wheels" -r "$path_selected")

	ensure_dir "$dir_wheels"
	if [[ -n "${WHEELHOUSE_PIP_PLATFORM:-}" ]]; then
		args_pip+=(
			--platform "$WHEELHOUSE_PIP_PLATFORM"
			--python-version "$TARGET_PYVER"
			--implementation "$TARGET_IMPL"
			--only-binary=:all:
		)
		[[ -n "${WHEELHOUSE_PIP_ABI:-}" ]] && args_pip+=(--abi "$WHEELHOUSE_PIP_ABI")
	fi
	print_status "info" "Downloading wheels to $dir_wheels ..."
	"$PYTHON" "${args_pip[@]}"
}

build_wheelhouse() {
	local dir_tmp dir_wheels

	print_status "section" "Building offline wheelhouse -> $WHEELHOUSE_DIR"
	ensure_dir "$WHEELHOUSE_DIR"
	dir_tmp="$(mktemp -d)"
	trap 'rm -rf "$dir_tmp"' EXIT
	dir_wheels="$dir_tmp/wheels"

	resolve_target_env
	driver_prune_list
	export_and_select "$dir_tmp/requirements.txt" "$dir_tmp/selected.txt"
	download_wheels "$dir_tmp/selected.txt" "$dir_wheels"

	print_status "info" "Packing the wheelhouse (${WHEELHOUSE_PART_MB} MB parts) ..."
	"$PYTHON" "$SELECT_PY" pack \
		--wheels-dir "$dir_wheels" \
		--zip-path "$WHEELHOUSE_DIR/wheelhouse.zip" \
		--manifest "$WHEELHOUSE_DIR/manifest.json" \
		--part-size-mb "$WHEELHOUSE_PART_MB"

	print_status "success" "Wheelhouse ready: $WHEELHOUSE_DIR (copy it beside the offline clone)"
}

assemble_wheelhouse() {
	local dir_source="${1:-$WHEELHOUSE_DIR}"
	local dir_out="${2:-$WHEELHOUSE_DIR/wheels}"

	print_status "section" "Assembling offline wheelhouse from $dir_source"
	"$PYTHON" "$SELECT_PY" assemble \
		--source "$dir_source" --wheels-out "$dir_out" \
		--manifest "$dir_source/manifest.json"
	print_status "success" "Wheels ready at $dir_out — install with:"
	print_status "info" "  pip install --no-index --find-links $dir_out -r requirements-lock.txt"
}

main() {
	bootstrap_init
	case "${1:-build}" in
		build) build_wheelhouse ;;
		assemble)
			shift
			assemble_wheelhouse "$@"
			;;
		*)
			print_status "error" "Usage: build_wheelhouse.sh [build|assemble [source] [wheels-out]]"
			return 2
			;;
	esac
}

main "$@"

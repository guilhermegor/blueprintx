#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

run_list() {
	local str_scaffold="$1" str_key="${2:-}"
	(
		cd "$WORK_DIR/cwd" || exit 1
		export HOME="$WORK_DIR/home"
		export GITGUARDIAN_API_KEY=$str_key
		bash "$REPO_ROOT/bin/scaffold/$str_scaffold.sh" --list-copies
	)
}

check_scaffold() {
	local str_scaffold="$1"
	shift
	local str_out str_keyed str_path
	rm -rf "${WORK_DIR:?}/cwd" "${WORK_DIR:?}/home"
	mkdir -p "$WORK_DIR/cwd" "$WORK_DIR/home"

	if ! str_out="$(run_list "$str_scaffold" 2>&1)"; then
		fail "$str_scaffold" "--list-copies exited non-zero: $str_out"
		return
	fi
	[[ -n "$str_out" ]] || { fail "$str_scaffold" "empty output"; return; }

	if [[ -n "$(find "$WORK_DIR/cwd" "$WORK_DIR/home" -mindepth 1 -print -quit)" ]]; then
		fail "$str_scaffold" "wrote files into cwd or HOME"
		return
	fi

	str_keyed="$(run_list "$str_scaffold" sentinel-key 2>&1)"
	[[ "$str_out" == "$str_keyed" ]] || { fail "$str_scaffold" "output depends on the API key"; return; }

	for str_path in "$@"; do
		if ! grep -qF -- "	$str_path" <<<"$str_out"; then
			fail "$str_scaffold" "missing copy target: $str_path"
			return
		fi
	done
	pass "$str_scaffold"
}

check_scaffold python_api_service ".gitignore" ".layer-policy.yaml" "src/utils/dtypes.py"
check_scaffold python_ddd_service ".gitignore" "AGENTS.md" "src/utils/dtypes.py"
check_scaffold python_ddd_service_orm ".gitignore" "AGENTS.md" "src/utils/dtypes.py"
check_scaffold python_mvc_service ".gitignore" "AGENTS.md" "src/utils/dtypes.py"
check_scaffold python_mvc_service_orm ".gitignore" "AGENTS.md" "src/utils/dtypes.py"
check_scaffold python_lib_minimal ".gitignore"
check_scaffold ts_react_app ".gitignore"
check_scaffold ts_lib ".gitignore"
check_scaffold bash_cli ".gitignore" ".pre-commit-config.yaml"
check_scaffold etcher_chromeos ".gitignore" "bin/fetch_tools.sh"
check_scaffold ventoy_usb ".gitignore" "lib/drive.sh" "sources.manifest"

((int_failures == 0)) || { echo "$int_failures failure(s)"; exit 1; }
echo "all list-copies checks passed"

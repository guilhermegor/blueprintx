#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON="$REPO_ROOT/templates/python-common"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

compose() {
	local str_overlay="$1" str_out="$2"
	{
		cat "$COMMON/ruff.toml"
		PROJECT_PKG_NAME=mypkg envsubst '${PROJECT_PKG_NAME}' <"$COMMON/ruff/$str_overlay.toml"
	} >"$str_out"
}

flags_banned_import() {
	local str_toml="$1" str_dir="$2" str_out
	str_out="$(cd "$str_dir" && ruff check --no-cache --config "$str_toml" --select TID251 --output-format json consumer.py 2>&1)" || true
	[[ "$str_out" == *\"TID251\"* ]]
}

for path_overlay in "$COMMON"/ruff/*.toml; do
	str_name="$(basename "$path_overlay" .toml)"
	str_toml="$WORK_DIR/$str_name.toml"
	compose "$str_name" "$str_toml"
	if ! python3 -c 'import sys, tomllib; tomllib.load(open(sys.argv[1], "rb"))' "$str_toml"; then
		fail "$str_name" "composed ruff.toml does not parse as TOML"
		continue
	fi
	if ! ruff check --no-cache --config "$str_toml" --show-settings "$COMMON/ruff.toml" >/dev/null 2>&1; then
		fail "$str_name" "ruff rejects the composed config"
		continue
	fi
	pass "$str_name composes, parses, and ruff accepts it"
done

mkdir -p "$WORK_DIR/lib/mypkg/_internal/utils" "$WORK_DIR/svc/utils"
printf 'class FileContract:\n    pass\n' >"$WORK_DIR/lib/mypkg/_internal/utils/tabular_reader.py"
printf 'from mypkg._internal.utils.tabular_reader import FileContract\n' >"$WORK_DIR/lib/consumer.py"
printf 'class FileContract:\n    pass\n' >"$WORK_DIR/svc/utils/tabular_reader.py"
printf 'from utils.tabular_reader import FileContract\n' >"$WORK_DIR/svc/consumer.py"

if flags_banned_import "$WORK_DIR/lib-minimal.toml" "$WORK_DIR/lib"; then
	pass "lib-minimal flags <pkg>._internal.utils.tabular_reader.FileContract"
else
	fail "lib-minimal" "the FileContract ban never fires on the real internal path"
fi

if flags_banned_import "$WORK_DIR/ddd-api-service.toml" "$WORK_DIR/svc"; then
	pass "ddd-api-service flags utils.tabular_reader.FileContract"
else
	fail "ddd-api-service" "the FileContract ban stopped firing"
fi

((int_failures == 0)) || { echo "$int_failures failure(s)"; exit 1; }
echo "all ruff overlay checks passed"

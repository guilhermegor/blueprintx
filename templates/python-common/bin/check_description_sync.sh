#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

ROOT="${1:-.}"

manifest_description() {
	python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys
import tomllib

path_root = pathlib.Path(sys.argv[1])
path_toml = path_root / "pyproject.toml"
path_json = path_root / "package.json"
if path_toml.is_file():
    dict_toml = tomllib.loads(path_toml.read_text(encoding="utf-8"))
    dict_meta = dict_toml.get("project") or dict_toml.get("tool", {}).get("poetry", {})
    sys.stdout.write(dict_meta.get("description", ""))
elif path_json.is_file():
    sys.stdout.write(json.loads(path_json.read_text(encoding="utf-8")).get("description", ""))
else:
    sys.exit(3)
PY
}

mkdocs_description() {
	python3 - "$ROOT/mkdocs.yml" <<'PY'
import json
import re
import sys

for str_line in open(sys.argv[1], encoding="utf-8"):
    match = re.match(r"site_description:\s*(.*?)\s*$", str_line)
    if not match:
        continue
    str_value = match.group(1)
    if str_value.startswith('"'):
        str_value = json.loads(str_value)
    elif str_value.startswith("'"):
        str_value = str_value[1:-1].replace("''", "'")
    sys.stdout.write(str_value)
    sys.exit(0)
sys.exit(4)
PY
}

github_about() {
	local str_slug
	str_slug="$(git -C "$ROOT" remote get-url origin 2>/dev/null |
		sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')" || true
	if [[ -z "$str_slug" || "$str_slug" == *:* || "$str_slug" == */*/* ]]; then
		return 3
	fi
	if [[ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]] || ! command -v gh >/dev/null 2>&1; then
		return 3
	fi
	GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}" gh api "repos/$str_slug" --jq '.description // ""'
}

compare() {
	local str_label="$1" str_expected="$2" str_actual="$3"
	if [[ "$str_expected" == "$str_actual" ]]; then
		print_status "success" "$str_label matches the manifest description"
		return 0
	fi
	print_status "error" "$str_label differs from the manifest description"
	print_status "error" "  manifest: $str_expected"
	print_status "error" "  $str_label: $str_actual"
	return 1
}

main() {
	local str_manifest str_other int_status=0 int_compared=0

	str_manifest="$(manifest_description)" || {
		print_status "warning" "SKIPPED description sync: no pyproject.toml or package.json in $ROOT"
		return 0
	}

	if str_other="$(mkdocs_description)"; then
		compare "mkdocs.yml site_description" "$str_manifest" "$str_other" || int_status=1
		int_compared=$((int_compared + 1))
	else
		print_status "warning" "SKIPPED mkdocs.yml comparison: no site_description in $ROOT/mkdocs.yml"
	fi

	if str_other="$(github_about)"; then
		compare "GitHub About" "$str_manifest" "$str_other" || int_status=1
		int_compared=$((int_compared + 1))
	else
		print_status "warning" "SKIPPED GitHub About comparison: needs a github.com origin remote, gh and GH_TOKEN/GITHUB_TOKEN"
	fi

	if [[ "$int_compared" -eq 0 ]]; then
		print_status "warning" "description sync compared nothing: every counterpart was skipped"
	fi
	return "$int_status"
}

main "$@"

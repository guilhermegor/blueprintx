#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
# shellcheck source=bin/lib/spec.sh
source "$REPO_ROOT/bin/lib/spec.sh"

STR_DESC="Pete's \"fast\" parser: C:\\tmp #1"
LIST_PY_TIERS=(lib-minimal api-service-native-db ddd-service-native-db ddd-service-orm-db
	mvc-service-native-db mvc-service-orm-db)
int_failures=0

fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

scaffold() {
	local str_tier="$1" path_out="$2" str_scaffold
	str_scaffold="$(grep '^scaffold=' "$REPO_ROOT/templates/$str_tier/skeleton.meta" | cut -d= -f2-)"
	mkdir -p "$path_out"
	if spec_skeleton_supported "$str_tier"; then
		spec_stdin_for_skeleton "$str_tier" ""
	else
		printf '\n\n\n\n\n\n\n\n'
	fi |
		BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot \
			LINKEDIN_URL=https://www.linkedin.com/in/ci-bot \
			bash "$REPO_ROOT/$str_scaffold" "$path_out" "desc-proj" "$STR_DESC" "0.0.1" \
			>"$path_out/scaffold.log" 2>&1
}

slot_values() {
	python3 - "$1" "$STR_DESC" <<'PY'
import json
import pathlib
import re
import sys
import tomllib

path_project = pathlib.Path(sys.argv[1]) / "desc-proj"
str_desc = sys.argv[2]
dict_slots = {}
if (path_project / "pyproject.toml").is_file():
    dict_toml = tomllib.loads((path_project / "pyproject.toml").read_text(encoding="utf-8"))
    dict_slots["pyproject.toml"] = (
        dict_toml.get("project") or dict_toml["tool"]["poetry"]
    )["description"]
if (path_project / "package.json").is_file():
    dict_slots["package.json"] = json.loads(
        (path_project / "package.json").read_text(encoding="utf-8")
    )["description"]
if (path_project / "mkdocs.yml").is_file():
    for str_line in (path_project / "mkdocs.yml").read_text(encoding="utf-8").splitlines():
        if str_line.startswith("site_description:"):
            dict_slots["mkdocs.yml"] = json.loads(str_line.split(":", 1)[1].strip())
if (path_project / "docusaurus.config.js").is_file():
    str_js = (path_project / "docusaurus.config.js").read_text(encoding="utf-8")
    match = re.search(r"tagline: '((?:[^'\\]|\\.)*)'", str_js)
    dict_slots["docusaurus tagline"] = json.loads(
        '"' + match.group(1).replace("\\'", "'") + '"'
    )
str_readme = (path_project / "README.md").read_text(encoding="utf-8")
dict_slots["README.md"] = str_desc if str_desc in str_readme else "MISSING"
for str_slot, str_value in dict_slots.items():
    print(f"{str_slot}\t{'OK' if str_value == str_desc else str_value}")
PY
}

check_tier() {
	local str_tier="$1" path_out="$WORK_DIR/$1" str_line
	if ! scaffold "$str_tier" "$path_out"; then
		fail "$str_tier" "scaffold exited non-zero: $(tail -3 "$path_out/scaffold.log" | tr '\n' '|')"
		return
	fi
	while IFS=$'\t' read -r str_slot str_got; do
		[[ "$str_got" == "OK" ]] || fail "$str_tier" "$str_slot carries '$str_got'"
	done < <(slot_values "$path_out")
	str_line="$(slot_values "$path_out" | wc -l)"
	if [[ "$str_line" -lt 2 ]]; then
		fail "$str_tier" "only $str_line slot(s) found"
		return
	fi
	echo "ok: $str_tier checked $str_line slot(s)"
}

check_drift_gate() {
	local path_project="$WORK_DIR/lib-minimal/desc-proj"
	if ! bash "$path_project/bin/check_description_sync.sh" "$path_project" >/dev/null 2>&1; then
		fail "drift gate" "rejected a freshly scaffolded project"
	fi
	python3 -c 'import pathlib, re, sys; p = pathlib.Path(sys.argv[1]); p.write_text(re.sub(r"(?m)^(site_description:.*)$", r"\1 # note", p.read_text(), count=1))' "$path_project/mkdocs.yml"
	if ! bash "$path_project/bin/check_description_sync.sh" "$path_project" >/dev/null 2>&1; then
		fail "drift gate" "rejected a matching site_description followed by a YAML comment"
	fi
	sed -i 's|^site_description: .*|site_description: "drifted" # note|' "$path_project/mkdocs.yml"
	if bash "$path_project/bin/check_description_sync.sh" "$path_project" >/dev/null 2>&1; then
		fail "drift gate" "accepted a commented mkdocs.yml that diverged from pyproject.toml"
	fi
	sed -i 's|^site_description: .*|site_description: "unterminated|' "$path_project/mkdocs.yml"
	if bash "$path_project/bin/check_description_sync.sh" "$path_project" >/dev/null 2>&1; then
		fail "drift gate" "accepted an unparseable site_description as absent"
	fi
	sed -i 's|^site_description: .*|site_description: "drifted"|' "$path_project/mkdocs.yml"
	if bash "$path_project/bin/check_description_sync.sh" "$path_project" >/dev/null 2>&1; then
		fail "drift gate" "accepted a mkdocs.yml that diverged from pyproject.toml"
	fi
	local str_out
	str_out="$(bash "$path_project/bin/check_description_sync.sh" "$WORK_DIR" 2>&1)"
	[[ "$str_out" == *SKIPPED* ]] || fail "drift gate" "an empty root passed without naming a skip"
	echo "ok: drift gate passes, fails on divergence, names what it skipped"
}

main() {
	local str_tier
	for str_tier in "${LIST_PY_TIERS[@]}" ts-lib react-spa-webpack; do
		check_tier "$str_tier"
	done
	check_drift_gate
	if [[ "$int_failures" -gt 0 ]]; then
		echo "$int_failures description-sync case(s) failed"
		exit 1
	fi
	echo "description reaches every slot in every tier"
}

main "$@"
